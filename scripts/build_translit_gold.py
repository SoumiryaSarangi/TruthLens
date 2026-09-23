"""Emit the transliteration gold the eval harness needs (FR-5).

    python scripts/build_translit_gold.py --dataset handtyped
    python scripts/build_translit_gold.py --dataset dakshina --lang pa

Output is `{uid, reference}` JSONL -- the same shape retrieval gold uses, which
is why `src/eval/evaluate.py` can read both with one loader.

Two sources, measuring genuinely different things, and the report keeps them
apart rather than averaging them into one number:

  handtyped  34 Punjabi forwards whose writer typed the SAME message twice,
             once in Latin letters and once in Gurmukhi. Sentence-level, real
             informal spelling, and the only Punjabi transliteration reference
             this project has. Small (34) -- always report the denominator.

  dakshina   Google's published romanization benchmark. Word-level and much
             larger, so it is the comparable number, but its romanizations are
             elicited rather than collected from real messages.

Written to data/gold/, which is gitignored: the handtyped references are
people's own writing and are never published.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from data.script_id import detect_script  # noqa: E402

GOLD = Path("data/gold")


def build_handtyped() -> int:
    split_path = Path("data/splits/handtyped/dev.jsonl")
    source = Path("data/raw/handtyped/forwards.csv")
    if not split_path.is_file() or not source.is_file():
        print(f"missing {split_path if not split_path.is_file() else source}")
        return 2

    with source.open("r", encoding="utf-8", newline="") as fh:
        native = {r["id"]: (r.get("native_script") or "").strip()
                  for r in csv.DictReader(fh)}

    out, skipped, latin = [], 0, []
    for row in load_jsonl(split_path):
        row_id = row["source_id"].split(":", 1)[1]
        reference = native.get(row_id, "")
        if not reference:
            skipped += 1
            continue
        # A "native script" cell that is dominantly Latin is not a usable
        # reference: it is either an untranslated row or one so code-mixed with
        # English that scoring a transliterator against it would measure the
        # English, not the transliteration. Reported, never silently kept.
        if detect_script(reference) == "latn":
            latin.append(row["uid"])
            continue
        out.append({"uid": row["uid"], "reference": reference})

    GOLD.mkdir(parents=True, exist_ok=True)
    dest = GOLD / "handtyped_dev_translit.jsonl"
    write_jsonl(dest, out)
    print(f"wrote {dest}  n={len(out)}")
    print(f"  no native-script rewrite supplied: {skipped} (not an error -- the "
          f"column is optional)")
    if latin:
        print(f"  excluded, reference is dominantly Latin: {len(latin)} "
              f"({', '.join(latin)})")
    langs: dict[str, int] = {}
    by_uid = {r["uid"]: r for r in load_jsonl(split_path)}
    for item in out:
        langs[by_uid[item["uid"]]["lang"]] = langs.get(by_uid[item["uid"]]["lang"], 0) + 1
    print(f"  by language: {langs}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_translit_gold.py")
    parser.add_argument("--dataset", required=True, choices=["handtyped"])
    args = parser.parse_args(argv)
    if args.dataset == "handtyped":
        return build_handtyped()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
