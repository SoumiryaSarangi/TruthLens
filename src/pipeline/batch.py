"""Run the pipeline over a frozen split and emit predictions JSONL.

    python -m pipeline.batch --stage retrieval --impl bm25 \
        --split data/splits/averitec/dev.jsonl --out results/preds/p1_bm25.jsonl

This is the join between the served pipeline and the offline harness
(SYSTEM_DESIGN.md §1, §9). It runs **the same orchestrator the API runs** —
there is no separate evaluation path that could drift from the demo.

Split files hold ids, not text (the Phase 0 decision), so claim text is
resolved from `data/interim/` exactly as the loaders do, and the evidence pool
is found through `source_id` → knowledge-store claim index.

`--stage retrieval` emits rankings; `--stage verdict` emits classifications.
`--stage both` does one pass and writes both, which matters because the pass
costs minutes and the two outputs come from identical work.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from common.io_jsonl import load_jsonl, write_jsonl
from common.seeds import set_all_seeds
from pipeline.contracts import Trace
from pipeline.orchestrator import Orchestrator, PipelineConfig
from retrieval.kb import claim_index_from_uid

INTERIM = Path("data/interim")


def load_texts(split_path: Path) -> dict[str, str]:
    """uid -> claim text, from the gitignored materialised text."""
    dataset = split_path.parent.name
    name = split_path.stem
    path = INTERIM / dataset / f"{name}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(
            f"no materialised text at {path}. Split files hold ids only; "
            "run `make data` to rebuild data/interim/."
        )
    return {r["uid"]: r["text"] for r in load_jsonl(path)}


def run_preprocess(
    split_path: Path,
    cfg: PipelineConfig,
    stage: str,
    out: Path,
    limit: int | None = None,
) -> dict[str, int]:
    """Score the language layer: `--stage lang` or `--stage translit`.

    Stops after preprocess instead of running `verify()`. Two reasons, and both
    are correctness rather than speed: the later stages resolve an AVeriTeC
    evidence pool from `source_id`, which MultiClaim and handtyped rows do not
    have, and running NLI over 3,153 rows to find out what language they are in
    would burn GPU to produce nothing.

    It is still the production stage object, built by the production config, so
    what is scored here is what the API runs.
    """
    set_all_seeds()
    rows = load_jsonl(split_path)
    if limit:
        rows = rows[:limit]
    texts = load_texts(split_path)
    orch = Orchestrator(cfg)

    predictions: list[dict] = []
    counts = {"n": 0, "degraded": 0, "no_output": 0}

    for row in rows:
        uid = row["uid"]
        text = texts.get(uid)
        if text is None:
            raise KeyError(f"{uid} has no text in data/interim/")

        trace = Trace(uid=uid, request_id=f"batch:{uid}")
        orch.preprocess.run(trace, text)
        counts["n"] += 1
        if any(e.note and "degraded" in e.note for e in trace.events):
            counts["degraded"] += 1

        pre = trace.pre
        if stage == "lang":
            predictions.append({"uid": uid, "pred": pre.lang,
                                "script": pre.script, "purity": pre.script_purity})
        else:
            if pre.transliterated is None:
                # Emitted, not skipped. A transliterator that declines is a
                # result -- dropping those rows would quietly raise the score by
                # scoring only the inputs it happened to like.
                counts["no_output"] += 1
            predictions.append({"uid": uid,
                                "transliterated": pre.transliterated or pre.normalized})

    write_jsonl(out, predictions)
    print(f"  wrote {len(predictions)} rows -> {out}")
    return counts


def run_claims(
    split_path: Path,
    cfg: PipelineConfig,
    stage: str,
    out: Path,
    limit: int | None = None,
    gate: bool = False,
) -> dict[str, int]:
    """Score the claims stage: `--stage checkworthy`, `span` or `normalize`.

    Stops after claims, for the same reason `run_preprocess` stops after
    preprocess: the later stages want an AVeriTeC evidence pool that X-CLAIM
    rows do not have, and running retrieval to find out whether a post contains
    a claim would burn GPU to produce nothing.

    `span` emits one BIO tag per WHITESPACE token, because that is X-CLAIM's
    tokenisation and the gold is aligned to it. Any model that tokenises
    differently has to project back onto these tokens before emitting.
    """
    set_all_seeds()
    rows = load_jsonl(split_path)
    if limit:
        rows = rows[:limit]
    texts = load_texts(split_path)
    orch = Orchestrator(cfg)

    predictions: list[dict] = []
    counts = {"n": 0, "checkworthy": 0, "capped": 0}

    for row in rows:
        uid = row["uid"]
        text = texts.get(uid)
        if text is None:
            raise KeyError(f"{uid} has no text in data/interim/")

        trace = Trace(request_id=f"batch:{uid}")
        orch.preprocess.run(trace, text)
        counts["n"] += 1

        if stage == "checkworthy":
            worthy = orch.claims.check_worthy(trace)
            trace.checkworthy = worthy
            counts["checkworthy"] += bool(worthy)
            predictions.append({"uid": uid, "pred": "Yes" if worthy else "No"})
            continue

        # Span and normalization measure FR-7, so they run the extractor
        # UNCONDITIONALLY unless `gate` is set. Running the check-worthiness gate
        # first is correct for the served pipeline -- FR-6 short-circuits before
        # retrieval -- but it confounds the FR-7 number badly: gating suppressed
        # extraction on 59 of 600 X-CLAIM dev rows, every one of which then
        # scored as an all-`O` prediction, and the joint arm's token F1 fell from
        # 0.7469 to 0.6801 without the span model changing at all. Two questions,
        # two measurements. `--gate` gives the end-to-end figure on purpose.
        if gate:
            worthy = orch.claims.check_worthy(trace)
            trace.checkworthy = worthy
            counts["checkworthy"] += bool(worthy)
            if not worthy:
                predictions.append(
                    {"uid": uid, "bio": ["O"] * len(text.split())} if stage == "span"
                    else {"uid": uid, "normalized": ""}
                )
                continue
        orch.claims.extract(trace)
        if trace.unchecked_claims:
            counts["capped"] += 1

        if stage == "span":
            predictions.append({"uid": uid, "bio": _span_tags(orch.claims, text, trace)})
        else:
            best = max((c.text for c in trace.claims), key=len, default="")
            predictions.append({"uid": uid, "normalized": best or text})

    write_jsonl(out, predictions)
    print(f"  wrote {len(predictions)} rows -> {out}")
    return counts


def _span_tags(stage, text: str, trace: Trace) -> list[str]:
    """The tagger's own token predictions where the impl has them.

    FR-7's span metric must measure what the span model predicts, not what
    survives being turned into `Claim` objects. `extract()` caps at MAX_CLAIMS
    and falls back to the whole post when it finds nothing -- both correct for
    PRODUCING claims, both wrong for scoring a tagger. Measured on the joint
    arm: raw tags score P 0.7747 / R 0.7199 / F1 0.7463, while the same model
    routed through extract() scores P 0.6284 / R 0.7998 / F1 0.7038. The
    round-trip trades precision for recall by over-tagging, and it is the
    cap and the fallback doing it, not the model.

    An implementation without a tagger (the rules baseline) has no token-level
    prediction to report, so it falls back to projecting its claims.
    """
    tag = getattr(stage, "tag", None)
    if callable(tag):
        return tag(text.split())
    return _bio_over_tokens(text, trace)


def _bio_over_tokens(text: str, trace: Trace) -> list[str]:
    """Project the extracted claims onto the post's whitespace tokens.

    The gold is one tag per whitespace token of the ORIGINAL text, so the tags
    have to be indexed by that tokenisation and not by whatever the model used.
    Preprocessing may have rewritten the text (artefact stripping), so the
    claim's character offsets are located in the original by search rather than
    trusted from the preprocessed copy.
    """
    tokens = text.split()
    tags = ["O"] * len(tokens)
    if not trace.claims:
        return tags

    # Character offset of each token in the original text.
    offsets, cursor = [], 0
    for token in tokens:
        start = text.index(token, cursor)
        offsets.append((start, start + len(token)))
        cursor = start + len(token)

    for claim in trace.claims:
        found = text.find(claim.text)
        if found < 0:
            continue
        lo, hi = found, found + len(claim.text)
        covered = [i for i, (s, e) in enumerate(offsets) if s < hi and e > lo]
        for n, i in enumerate(covered):
            tags[i] = "B-CLAIM" if n == 0 and tags[i] == "O" else (
                tags[i] if tags[i] != "O" else "I-CLAIM")
    return tags


def run_fastpath(
    split_path: Path,
    cfg: PipelineConfig,
    out: Path,
    limit: int | None = None,
) -> dict[str, int]:
    """Claim matching through the MATCHER (`--stage fastpath`), for FR-8.

    Distinct from `--stage match`, which calls the retriever directly. That was
    right for Phase 2's embedding ladder -- the question there was purely which
    encoder ranks best -- but it means the thing being scored is not the thing
    the API runs, which is the one promise this module's docstring makes. The
    matcher adds the pieces that turn a ranking into an answer: the metadata
    join, the verdict mapping, and any reranking.

    Predictions are `{uid, ranked_ids, scores}`, the same shape the retrieval
    task takes, so one run feeds both `task: retrieval` and `task: fast_path`.
    The threshold is NOT applied here: the harness needs the score whether or
    not it clears the bar, or every eval would measure one operating point.
    """
    set_all_seeds()
    rows = load_jsonl(split_path)
    if limit:
        rows = rows[:limit]
    texts = load_texts(split_path)
    orch = Orchestrator(cfg)
    matcher = orch.matcher
    if not hasattr(matcher, "rank_batch"):
        raise SystemExit(
            f"matching impl {matcher.impl!r} has no rank_batch; --stage fastpath "
            "needs a real matcher (try --matching-impl factcheck)."
        )

    counts = {"n": 0, "degraded": 0, "no_verdict": 0, "no_candidates": 0}
    queries: list[str] = []
    uids: list[str] = []

    started = time.time()
    for row in rows:
        uid = row["uid"]
        text = texts.get(uid)
        if text is None:
            raise KeyError(f"{uid} has no text in data/interim/")
        trace = Trace(uid=uid, request_id=f"batch:{uid}")
        orch.preprocess.run(trace, text)
        counts["n"] += 1
        if any(e.note and "degraded" in e.note for e in trace.events):
            counts["degraded"] += 1
        queries.append(trace.pre.normalized)
        uids.append(uid)
    print(f"  preprocessed {len(queries)} rows in {time.time() - started:.1f}s",
          flush=True)

    started = time.time()
    ranked = matcher.rank_batch(queries)
    print(f"  matched in {(time.time() - started) / 60:.1f} min", flush=True)

    # What the matcher would actually SERVE for each row, counted here because
    # it is invisible to the harness: a top-1 whose publisher rating is outside
    # the verdict mapping declines the fast path even when its score is high.
    meta = matcher._load_meta()
    predictions: list[dict] = []
    for uid, candidates in zip(uids, ranked, strict=True):
        if not candidates:
            counts["no_candidates"] += 1
        elif matcher._to_match(candidates, meta) is None:
            counts["no_verdict"] += 1
        predictions.append({
            "uid": uid,
            "ranked_ids": [doc_id for doc_id, _ in candidates],
            "scores": [score for _, score in candidates],
        })

    write_jsonl(out, predictions)
    print(f"  wrote {len(predictions)} rows -> {out}")
    return counts


def run_match(
    split_path: Path,
    cfg: PipelineConfig,
    out: Path,
    limit: int | None = None,
    use_transliterated: bool = False,
) -> dict[str, int]:
    """Claim matching against the global fact-check index (`--stage match`).

    Preprocess runs per row, so the language layer applies exactly as it does in
    the API -- which matters, because whether the query is romanized or native
    script is the variable the whole Phase 2 table is about. Encoding is then
    batched in one call: a transformer's per-row cost is mostly launch overhead,
    and 3,153 single-row passes take minutes where one batched pass takes
    seconds. Same stage object, same encoder, same index; only the cost differs.
    """
    set_all_seeds()
    rows = load_jsonl(split_path)
    if limit:
        rows = rows[:limit]
    texts = load_texts(split_path)
    orch = Orchestrator(cfg)

    counts = {"n": 0, "degraded": 0, "transliterated": 0}
    queries: list[str] = []
    uids: list[str] = []

    started = time.time()
    for row in rows:
        uid = row["uid"]
        text = texts.get(uid)
        if text is None:
            raise KeyError(f"{uid} has no text in data/interim/")
        trace = Trace(uid=uid, request_id=f"batch:{uid}")
        orch.preprocess.run(trace, text)
        counts["n"] += 1
        if any(e.note and "degraded" in e.note for e in trace.events):
            counts["degraded"] += 1
        pre = trace.pre
        if pre.transliterated is not None:
            counts["transliterated"] += 1
        query = (pre.transliterated if use_transliterated and pre.transliterated
                 else pre.normalized)
        queries.append(query)
        uids.append(uid)
    print(f"  preprocessed {len(queries)} rows in {time.time() - started:.1f}s", flush=True)

    started = time.time()
    ranked = orch.retriever.rank_batch(queries, k=cfg.k)
    print(f"  ranked in {(time.time() - started) / 60:.1f} min", flush=True)

    write_jsonl(out, [
        {"uid": uid,
         "ranked_ids": [d.doc_id for d in docs],
         "scores": [d.score for d in docs]}
        for uid, docs in zip(uids, ranked, strict=True)
    ])
    print(f"  wrote {len(uids)} rows -> {out}")
    return counts


def run(
    split_path: Path,
    cfg: PipelineConfig,
    stage: str,
    out_retrieval: Path | None,
    out_verdict: Path | None,
    limit: int | None = None,
) -> dict[str, int]:
    set_all_seeds()
    rows = load_jsonl(split_path)
    if limit:
        rows = rows[:limit]
    texts = load_texts(split_path)
    orch = Orchestrator(cfg)

    retrieval_out: list[dict] = []
    verdict_out: list[dict] = []
    counts = {"n": 0, "no_pool": 0, "no_evidence": 0}
    started = time.time()

    for i, row in enumerate(rows, start=1):
        uid = row["uid"]
        text = texts.get(uid)
        if text is None:
            raise KeyError(f"{uid} has no text in data/interim/")

        claim_idx = claim_index_from_uid(row["source_id"])
        trace = orch.verify(text, claim_idx=claim_idx)
        counts["n"] += 1

        if not trace.results:
            counts["no_pool"] += 1
            continue
        result = trace.results[0]
        if not result.passages:
            counts["no_evidence"] += 1

        if out_retrieval is not None:
            retrieval_out.append({
                "uid": uid,
                "ranked_ids": [p.doc_id for p in result.passages],
                "scores": [p.retrieval_score for p in result.passages],
            })
        if out_verdict is not None:
            verdict_out.append({
                "uid": uid,
                "pred": result.verdict,
                "probs": {result.verdict: result.confidence},
            })

        if i % 25 == 0 or i == len(rows):
            rate = i / max(time.time() - started, 1e-6)
            print(f"  {i:4}/{len(rows)}  {rate:5.2f} claims/s  "
                  f"eta {(len(rows) - i) / max(rate, 1e-6) / 60:5.1f} min", flush=True)

    if out_retrieval is not None:
        write_jsonl(out_retrieval, retrieval_out)
        print(f"  wrote {len(retrieval_out)} rows -> {out_retrieval}")
    if out_verdict is not None:
        write_jsonl(out_verdict, verdict_out)
        print(f"  wrote {len(verdict_out)} rows -> {out_verdict}")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.batch")
    ap.add_argument("--split", required=True)
    ap.add_argument("--stage", default="both",
                    choices=["retrieval", "verdict", "both", "lang", "translit",
                             "match", "fastpath", "checkworthy", "span",
                             "normalize"])
    ap.add_argument("--impl", default=None, help="override the retrieval impl")
    ap.add_argument("--stance-impl", default=None, help="override the stance impl")
    ap.add_argument("--preprocess-impl", default=None, help="override the preprocess impl")
    ap.add_argument("--claims-impl", default=None, help="override the claims impl")
    ap.add_argument("--matching-impl", default=None, help="override the matching impl")
    ap.add_argument("--reranker", default=None,
                    help="reranker for the matching stage: none|nli|xlmr. The "
                         "bi-encoder score alone gates the fast path poorly")
    ap.add_argument("--gate", action="store_true",
                    help="run the check-worthiness gate before extracting, as the "
                         "served pipeline does. Off by default so the span and "
                         "normalization numbers measure FR-7 rather than FR-6")
    ap.add_argument("--cw-threshold", type=float, default=None,
                    help="P(entailment) above which the zero-shot NLI arm calls a "
                         "message check-worthy; chosen on the derived dev set only")
    ap.add_argument("--adapter", default=None,
                    help="LoRA adapter directory for the claims stage; required to "
                         "score an ablation arm, which otherwise loads the default")
    ap.add_argument("--encoder", default=None,
                    help="dense retrieval encoder: tfidf|word2vec|muril|labse|bge_m3")
    ap.add_argument("--use-transliterated", action="store_true",
                    help="query with the transliterated text instead of what was typed")
    ap.add_argument("--force-lang", default=None,
                    help="skip language ID and assert this language; isolates the "
                         "transliterator from the language ID that feeds it")
    ap.add_argument("--pipeline-config", default=None)
    ap.add_argument("--out", default=None, help="output for a single --stage")
    ap.add_argument("--out-retrieval", default=None)
    ap.add_argument("--out-verdict", default=None)
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    cfg = (PipelineConfig.load(args.pipeline_config) if args.pipeline_config
           else PipelineConfig())
    if args.impl:
        cfg.stages["retrieval"] = args.impl
    if args.stance_impl:
        cfg.stages["stance"] = args.stance_impl
    if args.preprocess_impl:
        cfg.stages["preprocess"] = args.preprocess_impl
    if args.claims_impl:
        cfg.stages["claims"] = args.claims_impl
    if args.matching_impl:
        cfg.stages["matching"] = args.matching_impl
    if args.reranker:
        cfg.stage_args.setdefault("matching", {})["reranker"] = args.reranker
    if args.adapter:
        cfg.stage_args.setdefault("claims", {})["adapter"] = args.adapter
    if args.cw_threshold is not None:
        cfg.stage_args.setdefault("claims", {})["threshold"] = args.cw_threshold
    if args.force_lang:
        cfg.stage_args.setdefault("preprocess", {})["force_lang"] = args.force_lang
    if args.encoder:
        cfg.stages["retrieval"] = "dense"
        cfg.stage_args.setdefault("retrieval", {})["encoder"] = args.encoder
    if args.k:
        cfg.k = args.k

    if args.stage in ("checkworthy", "span", "normalize"):
        out = Path(args.out or f"results/preds/{args.stage}.jsonl")
        print(f"pipeline: preprocess={cfg.stages['preprocess']} "
              f"claims={cfg.stages['claims']} stage={args.stage}")
        counts = run_claims(Path(args.split), cfg, args.stage, out, args.limit,
                            gate=args.gate)
        print(f"  {counts['n']} rows | {counts['checkworthy']} check-worthy "
              f"| {counts['capped']} capped at MAX_CLAIMS")
        return 0

    if args.stage == "fastpath":
        out = Path(args.out or "results/preds/fastpath.jsonl")
        print(f"pipeline: preprocess={cfg.stages['preprocess']} "
              f"matching={cfg.stages['matching']} "
              f"reranker={cfg.stage_args.get('matching', {}).get('reranker', 'none')} "
              f"k={cfg.k}")
        counts = run_fastpath(Path(args.split), cfg, out, args.limit)
        print(f"  {counts['n']} rows | {counts['degraded']} degraded "
              f"| {counts['no_verdict']} top-1 declined for an unmappable rating "
              f"| {counts['no_candidates']} with no candidates")
        return 0

    if args.stage == "match":
        out = Path(args.out or "results/preds/match.jsonl")
        print(f"pipeline: preprocess={cfg.stages['preprocess']} "
              f"retrieval={cfg.stages['retrieval']} "
              f"encoder={cfg.stage_args.get('retrieval', {}).get('encoder')} k={cfg.k}")
        counts = run_match(Path(args.split), cfg, out, args.limit, args.use_transliterated)
        print(f"  {counts['n']} rows | {counts['degraded']} degraded "
              f"| {counts['transliterated']} transliterated")
        return 0

    if args.stage in ("lang", "translit"):
        out = Path(args.out or f"results/preds/{args.stage}.jsonl")
        print(f"pipeline: preprocess={cfg.stages['preprocess']}  stage={args.stage}")
        counts = run_preprocess(Path(args.split), cfg, args.stage, out, args.limit)
        print(f"  {counts['n']} rows | {counts['degraded']} degraded "
              f"| {counts['no_output']} with no transliteration")
        if counts["degraded"]:
            # Loud on purpose. A model that fails to load degrades to the script
            # heuristic, which produces a complete, plausible predictions file
            # that is not measuring the thing the config says it is.
            print(f"  WARNING: {counts['degraded']}/{counts['n']} rows ran DEGRADED. "
                  f"This number is not the implementation you asked for.")
        return 0

    out_r = out_v = None
    if args.stage in ("retrieval", "both"):
        out_r = Path(args.out_retrieval or (args.out if args.stage == "retrieval" else None)
                     or "results/preds/retrieval.jsonl")
    if args.stage in ("verdict", "both"):
        out_v = Path(args.out_verdict or (args.out if args.stage == "verdict" else None)
                     or "results/preds/verdict.jsonl")

    print(f"pipeline: {cfg.stages}  k={cfg.k}")
    counts = run(Path(args.split), cfg, args.stage, out_r, out_v, args.limit)
    print(f"  {counts['n']} claims | {counts['no_evidence']} with no evidence "
          f"| {counts['no_pool']} with no result")
    return 0


if __name__ == "__main__":
    sys.exit(main())
