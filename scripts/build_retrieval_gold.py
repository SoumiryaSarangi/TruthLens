"""Emit the retrieval gold file the eval harness needs.

    python scripts/build_retrieval_gold.py --split dev

For each claim in a frozen split, the gold evidence is the set of knowledge
store documents annotated `type == "gold"` -- AVeriTeC's own annotation, so
this is not gold we invented. Output is the `{uid, relevant_ids}` JSONL that
`src/eval/evaluate.py` already reads for retrieval tasks.

Written to data/gold/, which is gitignored: it is derived from the knowledge
store, and committing it would redistribute AVeriTeC URLs.

Claims with no gold document cannot be scored. They are reported and skipped
rather than emitted with an empty `relevant_ids`, because the harness would
then silently drop them from the denominator without saying so.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from retrieval.kb import KnowledgeStore, claim_index_from_uid  # noqa: E402


def build(split: str) -> int:
    split_path = Path(f"data/splits/averitec/{split}.jsonl")
    if not split_path.is_file():
        print(f"missing {split_path}")
        return 2

    store = KnowledgeStore(split)
    if not store.has_cache:
        print("no KB cache; run `python scripts/build_kb_cache.py` first "
              "(reading the zip directly would work but takes ~40 min)")
        return 2

    rows = load_jsonl(split_path)
    out, missing = [], []
    for row in rows:
        idx = claim_index_from_uid(row["source_id"])
        gold = store.gold_ids(idx)
        if not gold:
            missing.append(row["uid"])
            continue
        out.append({"uid": row["uid"], "relevant_ids": gold})

    dest = Path(f"data/gold/averitec_{split}_retrieval.jsonl")
    write_jsonl(dest, out)

    n_gold = sum(len(r["relevant_ids"]) for r in out)
    print(f"  {len(out)}/{len(rows)} claims scoreable -> {dest}")
    print(f"  {n_gold} gold documents, {n_gold / max(len(out), 1):.2f} per claim")
    if missing:
        print(f"  {len(missing)} claim(s) have NO gold and are excluded from "
              f"retrieval eval: {missing[:5]}")
    return 0


def build_multiclaim(split: str) -> int:
    """Gold for claim matching: the fact-checks a post was actually paired with.

    This is the first MULTILINGUAL retrieval task in the project. AVeriTeC is
    English only and X-CLAIM is a span task with no relevance judgements, so
    until MultiClaim arrived there was nothing to score the Phase 2 embedding
    comparison on in Hindi or Punjabi.
    """
    from data.multiclaim import load_pairs

    split_path = Path(f"data/splits/multiclaim/{split}.jsonl")
    if not split_path.is_file():
        print(f"missing {split_path}; run `python scripts/build_splits.py build "
              "--dataset multiclaim` first")
        return 2

    pairs: dict[str, list[str]] = {}
    for post_id, fc_id, _rel in load_pairs():
        pairs.setdefault(post_id, []).append(fc_id)

    rows = load_jsonl(split_path)
    out, missing = [], []
    for row in rows:
        post_id = row["source_id"].rsplit(":", 1)[1]
        gold = sorted(set(pairs.get(post_id, [])))
        if not gold:
            missing.append(row["uid"])
            continue
        out.append({"uid": row["uid"], "relevant_ids": gold})

    dest = Path(f"data/gold/multiclaim_{split}_retrieval.jsonl")
    write_jsonl(dest, out)
    n_gold = sum(len(r["relevant_ids"]) for r in out)
    by_lang: dict[str, int] = {}
    for row in rows:
        by_lang[row["lang"]] = by_lang.get(row["lang"], 0) + 1
    print(f"  {len(out)}/{len(rows)} posts scoreable -> {dest}")
    print(f"  {n_gold} gold fact-checks, {n_gold / max(len(out), 1):.2f} per post")
    print(f"  posts by language: {by_lang}")
    if missing:
        print(f"  {len(missing)} post(s) have no pair and are excluded")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/build_retrieval_gold.py")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--dataset", default="averitec", choices=["averitec", "multiclaim"])
    args = ap.parse_args(argv)
    if args.dataset == "multiclaim":
        return build_multiclaim(args.split)
    return build(args.split)


if __name__ == "__main__":
    raise SystemExit(main())
