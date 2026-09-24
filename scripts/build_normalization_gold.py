"""Emit the claim-normalization gold the eval harness needs (FR-7).

    python scripts/build_normalization_gold.py --split dev

CheckThat! 2025 Task 2 pairs a noisy post with a clean, standalone claim. The
loader keeps only the post -- `Row` has one text slot -- so the reference lives
only in `data/raw/checkthat25_t2/`. This recovers it through `source_id` and
writes `{uid, reference}` to gitignored `data/gold/`, the same shape the
transliteration gold uses.

The test split is read from `test_gold-*.csv`. `test-*.csv` is the shared-task
release and carries a `post` column only, so a builder pointed at it would
produce an empty gold file and no error.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402

RAW = Path("data/raw/checkthat25_t2")
SPLITS = Path("data/splits/checkthat25_t2")
GOLD = Path("data/gold")


def build(split: str) -> int:
    split_path = SPLITS / f"{split}.jsonl"
    if not split_path.is_file():
        print(f"missing {split_path}")
        return 2

    cache: dict[str, list[dict[str, str]]] = {}
    out, missing = [], 0
    for row in load_jsonl(split_path):
        _, file_part, index = row["source_id"].split(":")
        if file_part not in cache:
            path = RAW / f"{file_part}.csv"
            with path.open("r", encoding="utf-8", newline="") as fh:
                cache[file_part] = list(csv.DictReader(fh))
        rows = cache[file_part]
        i = int(index)
        reference = (rows[i].get("normalized claim") or "").strip() if i < len(rows) else ""
        if not reference:
            missing += 1
            continue
        out.append({"uid": row["uid"], "reference": reference})

    GOLD.mkdir(parents=True, exist_ok=True)
    dest = GOLD / f"checkthat25_t2_{split}_normalization.jsonl"
    write_jsonl(dest, out)
    print(f"wrote {dest}  n={len(out)}")
    if missing:
        print(f"  rows with no normalized claim: {missing}")
    lengths = sorted(len(r["reference"]) for r in out)
    print(f"  reference length: min {lengths[0]} median {lengths[len(lengths)//2]} "
          f"max {lengths[-1]} chars")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_normalization_gold.py")
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    args = parser.parse_args(argv)
    return build(args.split)


if __name__ == "__main__":
    raise SystemExit(main())
