"""Merge two scored-passages files into the combined stage's shape.

    python scripts/combine_scored.py --nli results/preds/p6_scored_dev_nli.jsonl \
        --xlmr results/preds/p6_scored_dev_xlmr.jsonl \
        --out results/preds/p6_scored_dev_xlmr_nli.jsonl

Exactly what `stance/combined.py` emits at serving time: NLI's distribution
under the plain keys, XLM-R's under `xlmr:`. The fold comes from the XLM-R file,
because XLM-R is the model that saw train claims; NLI is zero-shot. Rows must
align passage for passage -- both files were scored from the same cached
passages -- and anything else is refused.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from stance.combined import PREFIX  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/combine_scored.py")
    ap.add_argument("--nli", required=True)
    ap.add_argument("--xlmr", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    nli = {r["uid"]: r for r in load_jsonl(args.nli)}
    out = []
    for x in load_jsonl(args.xlmr):
        n = nli.get(x["uid"])
        if n is None or len(n["probs"]) != len(x["probs"]):
            raise SystemExit(f"{x['uid']}: the two files do not align passage for passage")
        out.append({
            "uid": x["uid"], "source_id": x["source_id"], "stance": "xlmr_nli",
            "fold": x["fold"], "dense": x["dense"],
            "probs": [{**np_, **{PREFIX + k: v for k, v in xp.items()}}
                      for np_, xp in zip(n["probs"], x["probs"], strict=True)],
        })
    if len(out) != len(nli):
        raise SystemExit(f"{len(nli) - len(out)} NLI rows have no XLM-R row")
    write_jsonl(Path(args.out), out)
    print(f"wrote {len(out)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
