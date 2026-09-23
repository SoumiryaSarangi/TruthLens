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
                    choices=["retrieval", "verdict", "both", "lang", "translit"])
    ap.add_argument("--impl", default=None, help="override the retrieval impl")
    ap.add_argument("--stance-impl", default=None, help="override the stance impl")
    ap.add_argument("--preprocess-impl", default=None, help="override the preprocess impl")
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
    if args.force_lang:
        cfg.stage_args.setdefault("preprocess", {})["force_lang"] = args.force_lang
    if args.k:
        cfg.k = args.k

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
