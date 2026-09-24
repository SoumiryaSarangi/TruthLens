"""Training pairs for the claim-matching reranker (FR-8).

    python scripts/mine_hard_negatives.py --split train

Writes `data/interim/reranker/{split}.jsonl`, gitignored: it embeds restricted
MultiClaim text.

## Why the negatives have to be HARD

A reranker exists to fix the bi-encoder's mistakes, so it has to be trained on
them. Random negatives are trivially separable -- a post about a vaccine rumour
against a fact-check about an election is not a distinction anyone needs a
cross-encoder for -- and a reranker trained on those learns to agree with the
retriever and adds nothing.

So the negatives are mined from the retriever itself: the top candidates it
returns for each training post that are NOT in that post's gold set. Those are
precisely the confusions the gate has to resolve, and they are the same shape as
the wrong top-1s measured in Phase 4 planning (mean cosine 0.6500 against 0.7239
for a correct one).

**If the reranker fails to beat the zero-shot control, suspect this file before
the model.** Negatives that are too easy is the failure mode that looks like a
model problem.

## What is NOT done here

No sampling from outside the retriever's top-k, and no "easy" negatives mixed
in. A reranker only ever sees the retriever's top-k at inference, so training it
on a distribution the retriever never produces would be training for a different
job. Stated because the usual recipe mixes in random negatives, and this
deliberately does not.
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from common.seeds import set_all_seeds  # noqa: E402

SPLITS = Path("data/splits/multiclaim")
INTERIM = Path("data/interim/multiclaim")
INDEX = Path("data/interim/index")
OUT = Path("data/interim/reranker")


def load_gold(split: str) -> dict[str, set[str]]:
    """uid -> the fact-checks it was annotated with.

    Built here rather than read from `data/gold/`, because only dev and test
    retrieval gold files exist -- train never needed one, since nothing was
    scored on it.
    """
    from data.multiclaim import load_pairs

    pairs: dict[str, set[str]] = collections.defaultdict(set)
    for post_id, fc_id, _ in load_pairs():
        pairs[post_id].add(fc_id)

    gold: dict[str, set[str]] = {}
    for row in load_jsonl(SPLITS / f"{split}.jsonl"):
        post_id = row["source_id"].rsplit(":", 1)[1]
        if pairs.get(post_id):
            gold[row["uid"]] = pairs[post_id]
    return gold


def mine(split: str, k: int, encoder: str, limit: int | None) -> int:
    set_all_seeds()
    split_path = SPLITS / f"{split}.jsonl"
    if not split_path.is_file():
        print(f"missing {split_path}")
        return 2

    texts = {r["uid"]: r["text"] for r in load_jsonl(INTERIM / f"{split}.jsonl")}
    # Only which ids have usable text is needed here, not the text -- holding
    # 78,077 full records alongside the index is most of a gigabyte.
    meta = {r["id"] for r in load_jsonl(INDEX / "factcheck_meta.jsonl")
            if r.get("text")}
    gold = load_gold(split)
    rows = [r for r in load_jsonl(split_path) if r["uid"] in gold]
    if limit:
        rows = rows[:limit]
    print(f"{split}: {len(rows)} posts with at least one annotated fact-check")

    from retrieval.dense import DenseRetriever

    retriever = DenseRetriever(encoder=encoder, k=k, index_dir=INDEX)
    queries = [texts[r["uid"]] for r in rows]
    started = time.time()
    ranked = retriever.rank_batch(queries, k=k)
    print(f"  retrieved in {(time.time() - started) / 60:.1f} min")

    out, counts = [], collections.Counter()
    for row, candidates in zip(rows, ranked, strict=True):
        uid = row["uid"]
        relevant = gold[uid]

        # Positives are the ANNOTATED fact-checks, not the ones the retriever
        # happened to find. Training only on golds the retriever already ranked
        # first would teach the reranker to reproduce the retriever, which is the
        # one thing it must not do.
        # Only IDS are stored, not the text. Writing the post beside each of its
        # ~11 candidates repeats it eleven times on disk, and holding all of it
        # in memory at once is what made the first attempt at this thrash a
        # 16 GB machine into swap. The trainer joins ids back to text.
        for fc_id in sorted(relevant):
            if fc_id in meta:
                out.append({"uid": uid, "fact_check_id": fc_id, "label": 1})
                counts["positive"] += 1

        for doc_id, score in ((d.doc_id, float(d.score)) for d in candidates):
            if doc_id in relevant:
                counts["gold_in_topk"] += 1
                continue
            if doc_id not in meta:
                continue
            out.append({"uid": uid, "fact_check_id": doc_id, "label": 0,
                        "retriever_score": round(score, 5)})
            counts["negative"] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{split}.jsonl"
    write_jsonl(dest, out)
    print(f"wrote {dest}  n={len(out)}")
    print(f"  positives {counts['positive']}, hard negatives {counts['negative']}, "
          f"ratio 1:{counts['negative'] / max(counts['positive'], 1):.1f}")
    print(f"  gold already in the retriever's top-{k}: {counts['gold_in_topk']} "
          f"({counts['gold_in_topk'] / max(counts['positive'], 1):.1%} of positives) "
          "-- the rest are misses the reranker cannot fix, only the retriever can")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/mine_hard_negatives.py")
    parser.add_argument("--split", default="train", choices=["train", "dev"])
    parser.add_argument("--k", type=int, default=10,
                        help="how deep to mine; matches the retrieval depth the "
                             "reranker will see at inference")
    parser.add_argument("--encoder", default="bge_m3")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    return mine(args.split, args.k, args.encoder, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
