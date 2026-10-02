"""Sample real failure cases for the error analysis (Phase 7), deterministically.

    python scripts/error_cases.py classification --split data/splits/averitec/dev.jsonl \
        --predictions results/preds/p6_verdict_served.jsonl \
        --control results/preds/p6_verdict_learned_xlmr_claimonly.jsonl \
        --passages results/preds/p6_passages_dev.jsonl --out reports/cases/verdict_dev.md
    python scripts/error_cases.py span --split data/splits/x_claim_romanized/dev.jsonl \
        --predictions results/preds/p7_span_romanized_joint.jsonl \
        --gold data/gold/x_claim_romanized_dev_span.jsonl --lang hi --out reports/cases/span_hi.md
    python scripts/error_cases.py retrieval --split data/splits/multiclaim/dev.jsonl \
        --predictions results/preds/p2_match_bge_m3.jsonl \
        --gold data/gold/multiclaim_dev_retrieval.jsonl --lang pa --out reports/cases/match_pa.md

Writes a Markdown case sheet to gitignored `reports/cases/` -- it quotes
dataset text, which never enters the repository (SRS C-4). Each case has an
empty `category:` line to fill in by hand from the taxonomy fixed BEFORE any
case was read (docs/error-analysis.md).

Selection is seeded (42) and stratified, so a re-run gives the same cases and
no one error type crowds out the rest. For verdicts the confident wrong
refutations of true claims come first and are listed IN FULL, because that is
the failure the Phase 6 decision named as the one to look at first.

The counts printed here describe the sample sheet; the reported confusion
counts come from the harness.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED  # noqa: E402

HIGH_BAND = 0.60      # app/main.py CONFIDENCE_BANDS["high"], the served cut


def _texts(split: Path) -> dict[str, str]:
    path = Path("data/interim") / split.parent.name / split.name
    return {r["uid"]: r["text"] for r in load_jsonl(path)} if path.is_file() else {}


def _stratified(groups: dict[tuple, list], n: int, rng: random.Random) -> list:
    """Round-robin over the groups (largest first), shuffled within each."""
    pools = {k: rng.sample(v, len(v)) for k, v in groups.items()}
    order = sorted(pools, key=lambda k: (-len(pools[k]), str(k)))
    out: list = []
    while len(out) < n and any(pools.values()):
        for k in order:
            if pools[k] and len(out) < n:
                out.append(pools[k].pop())
    return out


def classification(args, rows, texts, rng) -> list[str]:
    gold_field = args.gold_field
    preds = {r["uid"]: r for r in load_jsonl(args.predictions)}
    control = {r["uid"]: r for r in load_jsonl(args.control)} if args.control else {}
    passages = ({r["uid"]: r for r in load_jsonl(args.passages)} if args.passages else {})
    wrong = [r for r in rows if r["uid"] in preds and preds[r["uid"]]["pred"] != r[gold_field]]
    confident_true_refuted = [
        r for r in wrong if r[gold_field] == "Supported"
        and preds[r["uid"]]["pred"] == "Refuted"
        and preds[r["uid"]].get("confidence", 0) >= HIGH_BAND]
    rest = [r for r in wrong if r not in confident_true_refuted]
    groups: dict[tuple, list] = defaultdict(list)
    for r in rest:
        groups[(r[gold_field], preds[r["uid"]]["pred"])].append(r)
    picked = confident_true_refuted + _stratified(groups, args.n, rng)

    lines = [f"# Failure cases: {args.predictions}",
             f"{len(wrong)} wrong of {sum(1 for r in rows if r['uid'] in preds)} predicted; "
             f"{len(confident_true_refuted)} are TRUE claims refuted at confidence >= "
             f"{HIGH_BAND} (all listed first), then {len(picked) - len(confident_true_refuted)} "
             "stratified by (gold, predicted).", ""]
    for r in picked:
        p = preds[r["uid"]]
        c = control.get(r["uid"])
        lines += [f"## {r['uid']}  gold={r[gold_field]}  pred={p['pred']}  "
                  f"conf={p.get('confidence', float('nan')):.3f}",
                  f"> {texts.get(r['uid'], '(text not materialised)')}", ""]
        if c is not None:
            same = "SAME error" if c["pred"] == p["pred"] else "different"
            lines.append(f"- claim-only control: {c['pred']} ({same})")
        for k, psg in enumerate((passages.get(r["uid"], {}).get("passages") or [])[:3], 1):
            snippet = " ".join((psg.get("text") or "").split())[:200]
            lines.append(f"- [{k}] {psg.get('doc_id', '')[:80]} :: {snippet}")
        lines += ["- category: ", ""]
    return lines


def _f1(pred: list[str], gold: list[str]) -> float:
    p = {i for i, t in enumerate(pred) if t != "O"}
    g = {i for i, t in enumerate(gold) if t != "O"}
    if not p and not g:
        return 1.0
    tp = len(p & g)
    return 0.0 if not tp else 2 * tp / (len(p) + len(g))


def span(args, rows, texts, rng) -> list[str]:
    preds = {r["uid"]: r["bio"] for r in load_jsonl(args.predictions)}
    gold = {r["uid"]: r["bio"] for r in load_jsonl(args.gold)}
    scored = [(r, _f1(preds[r["uid"]], gold[r["uid"]])) for r in rows
              if r["uid"] in preds and r["uid"] in gold]
    bad = [(r, f) for r, f in scored if f < 0.5]
    groups: dict[tuple, list] = defaultdict(list)
    for r, f in bad:
        groups[(r["lang"], r["script"])].append((r, f))
    picked = _stratified(groups, args.n, rng)

    def mark(tokens: list[str], tags: list[str]) -> str:
        return " ".join(f"[{t}]" if tag != "O" else t for t, tag in zip(tokens, tags, strict=False))

    lines = [f"# Span failures (token F1 < 0.5): {args.predictions}",
             f"{len(bad)} of {len(scored)} posts; {len(picked)} sampled.", ""]
    for r, f in picked:
        tokens = texts.get(r["uid"], "").split()
        lines += [f"## {r['uid']}  {r['lang']}/{r['script']}  token F1 {f:.2f}",
                  f"- gold: {mark(tokens, gold[r['uid']])}",
                  f"- pred: {mark(tokens, preds[r['uid']])}", "- category: ", ""]
    return lines


def retrieval(args, rows, texts, rng) -> list[str]:
    preds = {r["uid"]: r for r in load_jsonl(args.predictions)}
    gold = {r["uid"]: set(r["relevant_ids"]) for r in load_jsonl(args.gold)}
    meta_path = Path("data/interim/index/factcheck_meta.jsonl")
    meta = {r["id"]: r for r in load_jsonl(meta_path)} if meta_path.is_file() else {}
    bad = [r for r in rows if r["uid"] in preds and r["uid"] in gold
           and (preds[r["uid"]]["ranked_ids"] or [None])[0] not in gold[r["uid"]]]
    groups: dict[tuple, list] = defaultdict(list)
    for r in bad:
        groups[(r["lang"], r["script"])].append(r)
    picked = _stratified(groups, args.n, rng)
    lines = [f"# Matching failures (top-1 not gold): {args.predictions}",
             f"{len(bad)} of {sum(1 for r in rows if r['uid'] in gold)}; {len(picked)} sampled.", ""]
    for r in picked:
        p = preds[r["uid"]]
        top = p["ranked_ids"][0] if p["ranked_ids"] else None
        rank = next((i + 1 for i, d in enumerate(p["ranked_ids"]) if d in gold[r["uid"]]), None)
        g = next(iter(gold[r["uid"]]))
        lines += [f"## {r['uid']}  {r['lang']}/{r['script']}  score {p['scores'][0]:.3f}  "
                  f"gold rank {rank or '>k'}",
                  f"> {texts.get(r['uid'], '')[:300]}",
                  f"- top-1: {meta.get(top, {}).get('title', top)}",
                  f"- gold : {meta.get(g, {}).get('title', g)}", "- category: ", ""]
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/error_cases.py")
    ap.add_argument("kind", choices=["classification", "span", "retrieval"])
    ap.add_argument("--split", required=True)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--gold", help="span / retrieval gold file")
    ap.add_argument("--gold-field", default="label")
    ap.add_argument("--control", help="classification: the claim-only control's predictions")
    ap.add_argument("--passages", help="classification: cached passages, to show evidence")
    ap.add_argument("--lang", help="only rows in this language")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    split = Path(args.split)
    rows = [r for r in load_jsonl(split) if not args.lang or r["lang"] == args.lang]
    rng = random.Random(SEED)
    texts = _texts(split)
    lines = {"classification": classification, "span": span,
             "retrieval": retrieval}[args.kind](args, rows, texts, rng)
    out = Path(args.out)
    if not str(out).replace("\\", "/").startswith("reports/"):
        raise SystemExit("case sheets quote dataset text: write them under reports/ (gitignored)")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}  ({lines[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
