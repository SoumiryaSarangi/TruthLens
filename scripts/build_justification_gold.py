"""Reference explanations for `task: faithfulness` chrF (Phase 6, FR-15).

    python scripts/build_justification_gold.py

Writes data/gold/averitec_dev_justification.jsonl: one cleaned AVeriTeC
justification per dev claim, as {"uid", "reference"}. Cleaned the same way the
explainer's training targets are (`clean_justification`), so chrF compares like
with like; the raw text is one function call away in data/raw/.

Dev only. The test references are built in Phase 7, alongside the one
test-split run CLAUDE.md allows.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import write_jsonl  # noqa: E402
from generation.explain_data import examples  # noqa: E402

OUT = Path("data/gold/averitec_dev_justification.jsonl")


def main() -> int:
    rows = [{"uid": ex["uid"], "reference": ex["target"]} for ex in examples("dev")]
    write_jsonl(OUT, rows)
    print(f"wrote {len(rows)} references -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
