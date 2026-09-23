"""Emit the claim-span gold the eval harness needs (FR-7).

    python scripts/build_span_gold.py --split dev

X-CLAIM is a span-identification dataset: each post comes with the token index
range that IS the claim. The loader keeps only the joined text, and the split
files carry ids and hashes -- so the annotation exists nowhere the harness can
reach it. This recovers it from `data/raw/x_claim/` through `source_id` and
writes `{uid, bio, tokens}` to gitignored `data/gold/`.

Gold is a **BIO tag sequence**, one tag per token, from the label set that
already exists (`src/data/labels.py`, `SPAN_BIO`). That is deliberate: the
harness normalises all gold to `dict[str, list[str]]`, and a tag sequence is a
list of strings, so this needs no new gold shape at all.

## The end index is INCLUSIVE, and that is measured rather than assumed

Nothing upstream documents it, and getting it wrong shifts every span by one
token while still looking entirely plausible. Counted across train-en:
`span_end_index == len(tokens)` occurs **0** times and
`== len(tokens) - 1` occurs **1,617** times. Exclusive indexing would produce
the opposite. `--check` re-runs that count so the assumption is re-tested
whenever the data changes, and the build refuses if it flips.
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from data.labels import SPAN_BIO  # noqa: E402

RAW = Path("data/raw/x_claim")
SPLITS = Path("data/splits/x_claim")
GOLD = Path("data/gold")

BEGIN, INSIDE, OUTSIDE = SPAN_BIO  # ("B-CLAIM", "I-CLAIM", "O")


class SpanConventionError(RuntimeError):
    """The inclusive-end convention no longer holds in the source data."""


def parse_row(item: dict[str, str]) -> tuple[list[str], int, int] | None:
    """(tokens, start, end_inclusive) for one raw X-CLAIM row."""
    try:
        tokens = ast.literal_eval(item["tokens"])
        starts = ast.literal_eval(item["span_start_index"])
        ends = ast.literal_eval(item["span_end_index"])
    except (ValueError, SyntaxError, KeyError):
        return None
    if not isinstance(tokens, list) or not tokens:
        return None
    # Measured: every row in every language carries exactly one span. A
    # multi-span row would need a different BIO construction, so it is reported
    # rather than silently taking the first.
    if len(starts) != 1 or len(ends) != 1:
        return None
    start, end = int(starts[0]), int(ends[0])
    if not (0 <= start <= end < len(tokens)):
        return None
    return [str(t) for t in tokens], start, end


def to_bio(n_tokens: int, start: int, end: int) -> list[str]:
    """BIO tags for one inclusive token span."""
    tags = [OUTSIDE] * n_tokens
    tags[start] = BEGIN
    for i in range(start + 1, end + 1):        # inclusive end
        tags[i] = INSIDE
    return tags


def check_convention(langs=("en", "hi", "pa"), splits=("train", "dev", "test")) -> dict:
    """Re-measure the inclusive-end evidence. Raises if it has flipped."""
    at_len = at_len_minus_1 = total = multi = 0
    for lang in langs:
        for split in splits:
            path = RAW / f"{split}-{lang}.csv"
            if not path.is_file():
                continue
            with path.open("r", encoding="utf-8", newline="") as fh:
                for item in csv.DictReader(fh):
                    try:
                        tokens = ast.literal_eval(item["tokens"])
                        ends = ast.literal_eval(item["span_end_index"])
                    except (ValueError, SyntaxError, KeyError):
                        continue
                    if len(ends) != 1:
                        multi += 1
                        continue
                    total += 1
                    if int(ends[0]) == len(tokens):
                        at_len += 1
                    elif int(ends[0]) == len(tokens) - 1:
                        at_len_minus_1 += 1
    if at_len:
        raise SpanConventionError(
            f"{at_len} row(s) have span_end_index == len(tokens), which is only "
            f"possible under EXCLUSIVE indexing. This builder assumes INCLUSIVE "
            f"(evidence: {at_len_minus_1} rows end at len(tokens)-1). The source "
            f"data changed; re-derive the convention before trusting any span "
            f"number built from it."
        )
    return {"rows": total, "end_at_len": at_len,
            "end_at_len_minus_1": at_len_minus_1, "multi_span": multi}


def raw_rows(lang: str, split: str) -> list[dict[str, str]]:
    path = RAW / f"{split}-{lang}.csv"
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build(split: str) -> int:
    split_path = SPLITS / f"{split}.jsonl"
    if not split_path.is_file():
        print(f"missing {split_path}")
        return 2

    evidence = check_convention()
    print(f"  convention check: {evidence['rows']} rows, "
          f"{evidence['end_at_len_minus_1']} end at len-1, "
          f"{evidence['end_at_len']} end at len -> INCLUSIVE confirmed")
    if evidence["multi_span"]:
        print(f"  NOTE: {evidence['multi_span']} multi-span row(s) skipped")

    cache: dict[str, list[dict[str, str]]] = {}
    out, unusable = [], Counter()
    for row in load_jsonl(split_path):
        # source_id is `x_claim:<split>-<lang>:<row index in that CSV>`.
        _, file_part, index = row["source_id"].split(":")
        lang = file_part.rsplit("-", 1)[1]
        if file_part not in cache:
            cache[file_part] = raw_rows(lang, file_part.rsplit("-", 1)[0])
        rows = cache[file_part]
        i = int(index)
        if i >= len(rows):
            unusable["index out of range"] += 1
            continue
        parsed = parse_row(rows[i])
        if parsed is None:
            unusable["unparseable or multi-span"] += 1
            continue
        tokens, start, end = parsed
        out.append({"uid": row["uid"], "bio": to_bio(len(tokens), start, end),
                    "tokens": tokens})

    GOLD.mkdir(parents=True, exist_ok=True)
    dest = GOLD / f"x_claim_{split}_span.jsonl"
    write_jsonl(dest, out)
    print(f"wrote {dest}  n={len(out)} of {sum(1 for _ in load_jsonl(split_path))}")
    for reason, n in unusable.items():
        print(f"  skipped, {reason}: {n}")

    covered = sum(sum(1 for t in r["bio"] if t != OUTSIDE) for r in out)
    tokens_total = sum(len(r["bio"]) for r in out)
    whole = sum(1 for r in out if all(t != OUTSIDE for t in r["bio"]))
    print(f"  claim tokens: {covered}/{tokens_total} = {covered / tokens_total:.1%}")
    print(f"  spans covering the WHOLE post: {whole}/{len(out)} = "
          f"{whole / len(out):.1%}  <- the whole_post_span baseline's free wins")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_span_gold.py")
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    parser.add_argument("--all", action="store_true", help="build every split")
    args = parser.parse_args(argv)
    splits = ("train", "dev", "test") if args.all else (args.split,)
    for split in splits:
        print(f"{split}:")
        code = build(split)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
