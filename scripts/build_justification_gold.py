"""Reference explanations for `task: faithfulness` chrF (Phase 6, FR-15).

    python scripts/build_justification_gold.py [--split dev|test]

Writes data/gold/averitec_<split>_justification.jsonl: one cleaned AVeriTeC
justification per claim, as {"uid", "reference"}. Cleaned the same way the
explainer's training targets are (`clean_justification`), so chrF compares like
with like; the raw text is one function call away in data/raw/.

Test references are built for the one test-split run CLAUDE.md allows (Phase
7). They are gold, read from AVeriTeC's train.json like every test claim; no
model sees them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import write_jsonl  # noqa: E402
from generation.explain_data import examples  # noqa: E402

GOLD = Path("data/gold")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/build_justification_gold.py")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    args = ap.parse_args(argv)
    out = GOLD / f"averitec_{args.split}_justification.jsonl"
    rows = [{"uid": ex["uid"], "reference": ex["target"]} for ex in examples(args.split)]
    write_jsonl(out, rows)
    print(f"wrote {len(rows)} references -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
