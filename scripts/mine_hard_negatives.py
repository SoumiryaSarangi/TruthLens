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

## Hard negatives alone handed the model a shortcut. Measured.

The first version mined ONLY top-k non-gold negatives, on the reasoning that a
reranker never sees anything else at inference. That reasoning is right about the
input distribution and wrong about the label distribution, and the trained model
exploited the difference.

Positives are the annotated golds; negatives are non-golds. So *"is this
fact-check ever somebody's answer"* predicts the label **without reading the post
at all**, and the model learned exactly that. Measured on the resulting reranker:

* candidates never a positive in training averaged P(relevant) 0.0500;
  candidates seen as a positive 2-4 times averaged 0.1596 (r = +0.250)
* across candidates appearing for 5+ dev posts, overall score SD was 0.224 while
  the mean WITHIN-candidate SD was 0.057 -- three quarters of the variation came
  from which fact-check it was, not from the pair
* its precision at its most confident operating point collapsed to 9.8%

A cross-encoder that does not have to look at the post cannot order candidates
within a query, which is the only thing a gate needs.

## `--gold-negatives` was the obvious fix and it is not enough. Also measured.

Sampling negatives from **other posts' gold**, frequency-weighted so a
fact-check's positive RATE stays roughly constant, should make identity
uninformative. Measured on the mined data, before spending another training run
on it:

    correlation between log(times a positive) and positive rate
      hard negatives only          r = +0.803
      plus 2 other-post-gold       r = +0.768

It reduces the GRADED part of the shortcut -- the spread of positive rate across
ever-gold candidates falls from sd 0.1645 to 0.1035 -- and leaves the dominant
part untouched, because **a candidate that is never any train post's gold has a
positive rate of exactly 0.0000 and no amount of negative sampling can change
that.** Identity still answers "could this ever be a positive".

So the shortcut lives in the OBJECTIVE, not the sampling. The fix is to train
within a query -- a listwise softmax over each post's candidate list with its gold
as the target -- so the model is scored on ordering candidates for one post, where
a global per-candidate prior has much less to offer. That is a Phase 6 change.

**The default is 0**, so this script reproduces the adapter that was actually
trained and reported. The flag stays because the measurement above is the
evidence for the objective change, and a rejected experiment with a number beside
it is worth more than a deleted one.
"""

from __future__ import annotations

import argparse
import collections
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402

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


def mine(split: str, k: int, encoder: str, limit: int | None,
         gold_negatives: int = 0) -> int:
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

    # A MULTISET, not a set: drawing uniformly from distinct golds would leave a
    # graded shortcut, because a fact-check that is gold for six posts would still
    # get six positives against the same two negatives as one that is gold once.
    # Sampling in proportion to how often a fact-check IS a positive makes its
    # positive RATE roughly constant across candidates, which is the property that
    # makes identity uninformative.
    gold_pool = [fc for ids in gold.values() for fc in ids if fc in meta]
    rng = random.Random(SEED)
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

        # Negatives drawn from OTHER posts' gold, so that being somebody's answer
        # stops predicting the label. Without these the model can score the
        # candidate alone and ignore the post; with them, a fact-check appears on
        # both sides of the label and its identity carries no information.
        for fc_id in rng.choices(gold_pool, k=gold_negatives) if gold_pool else ():
            if fc_id in relevant or fc_id not in meta:
                continue
            out.append({"uid": uid, "fact_check_id": fc_id, "label": 0,
                        "source": "other_post_gold"})
            counts["gold_negative"] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{split}.jsonl"
    write_jsonl(dest, out)
    print(f"wrote {dest}  n={len(out)}")
    negatives = counts["negative"] + counts["gold_negative"]
    print(f"  positives {counts['positive']}, hard negatives {counts['negative']}, "
          f"other-post-gold negatives {counts['gold_negative']}, "
          f"ratio 1:{negatives / max(counts['positive'], 1):.1f}")
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
    parser.add_argument("--gold-negatives", type=int, default=0,
                        help="negatives per post drawn from OTHER posts' gold, "
                             "frequency-weighted. Measured to reduce the "
                             "candidate-identity shortcut only slightly "
                             "(r +0.803 -> +0.768); see the module docstring")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    return mine(args.split, args.k, args.encoder, args.limit,
                gold_negatives=args.gold_negatives)


if __name__ == "__main__":
    raise SystemExit(main())
