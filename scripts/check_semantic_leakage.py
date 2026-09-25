"""Embedding-based near-duplicate detection across frozen splits (Phase 4).

    python scripts/check_semantic_leakage.py --dataset multiclaim
    python scripts/check_semantic_leakage.py --all --calibrate

`data/CLAUDE.md`: *"Embedding-based duplicate detection belongs in Phase 4
alongside the claim-matching retriever. Until then, `make leakage` passing means
no duplicates, not no overlap."* This is that check, using the encoder Phase 2
already chose.

## What the existing check does and does not catch

`src/data/leakage.py` compares 64-bit SimHashes, and its thresholds were
calibrated on this project's own text rather than assumed: trivial variants land
at 0-4 Hamming, word substitutions around 10, unrelated claims 22+. That catches
duplicates and near-copies. It cannot catch a paraphrase that shares no tokens,
which is exactly what a forwarded message becomes as it is retyped.

## Calibrated, not assumed -- the same discipline

A cosine threshold pulled out of the air would produce a number nobody could
defend. `--calibrate` measures two distributions on THIS corpus first:

  known near-duplicates   pairs the SimHash check already flags (Hamming <= 4)
  unrelated pairs         random pairs from the same dataset and split

and prints the percentiles, so the cut is chosen between two measured
distributions. Run it before believing any count this script reports.

## This script does not change anything

It reports. `CLAUDE.md`'s first non-negotiable is that a frozen split is never
regenerated without asking, and a finding here is a conversation, not a rebuild:
the splits are committed, every Phase 1-4 number is scored against them, and
rebuilding invalidates all of it. Read a finding as "quantify this limitation in
the report", unless it is large enough to be worth the full re-freeze ceremony.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402

SPLITS = Path("data/splits")
INTERIM = Path("data/interim")

# Provisional, and deliberately not a default anyone should trust: run
# --calibrate on the dataset in question and read the two distributions.
DEFAULT_CUT = 0.90


def load_texts(dataset: str, split: str) -> dict[str, str]:
    path = INTERIM / dataset / f"{split}.jsonl"
    if not path.is_file():
        return {}
    return {r["uid"]: r["text"] for r in load_jsonl(path)}


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def encode(texts: list[str], encoder: str, batch_size: int) -> np.ndarray:
    from retrieval.encoders import build_encoder

    model = build_encoder(encoder)
    return np.asarray(model.encode(texts, batch_size=batch_size), dtype=np.float32)


def max_similarity(eval_vecs: np.ndarray, train_vecs: np.ndarray,
                   chunk: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Best train match for each eval row. Vectors are already L2-normalised."""
    best = np.zeros(len(eval_vecs), dtype=np.float32)
    where = np.zeros(len(eval_vecs), dtype=np.int64)
    for start in range(0, len(eval_vecs), chunk):
        block = eval_vecs[start:start + chunk]
        scores = block @ train_vecs.T
        where[start:start + chunk] = scores.argmax(axis=1)
        best[start:start + chunk] = scores.max(axis=1)
    return best, where


def calibrate(dataset: str, encoder: str, batch_size: int, n_pairs: int) -> None:
    """Measure what a near-duplicate and an unrelated pair actually score here."""
    rows = list(load_jsonl(SPLITS / dataset / "train.jsonl"))
    texts = load_texts(dataset, "train")
    rows = [r for r in rows if r["uid"] in texts]
    if len(rows) < 2:
        print(f"  {dataset}: not enough text to calibrate")
        return

    rng = random.Random(SEED)
    # Known near-duplicates, per the SimHash thresholds already calibrated on
    # this corpus in Phase 0.
    by_hash: dict[str, list[dict]] = {}
    for row in rows:
        by_hash.setdefault(row["simhash64"][:4], []).append(row)
    near: list[tuple[str, str]] = []
    for bucket in by_hash.values():
        for i, a in enumerate(bucket):
            for b in bucket[i + 1:]:
                if hamming(a["simhash64"], b["simhash64"]) <= 4:
                    near.append((a["uid"], b["uid"]))
                if len(near) >= n_pairs:
                    break
            if len(near) >= n_pairs:
                break
        if len(near) >= n_pairs:
            break

    unrelated = [(rng.choice(rows)["uid"], rng.choice(rows)["uid"])
                 for _ in range(n_pairs)]
    unrelated = [(a, b) for a, b in unrelated if a != b]

    for name, pairs in (("known near-duplicates (SimHash <= 4)", near),
                        ("random unrelated pairs", unrelated)):
        if not pairs:
            print(f"  {name}: none found")
            continue
        left = encode([texts[a] for a, _ in pairs], encoder, batch_size)
        right = encode([texts[b] for _, b in pairs], encoder, batch_size)
        sims = np.sum(left * right, axis=1)
        sims.sort()
        print(f"  {name} (n={len(sims)}): "
              f"p5 {sims[int(0.05 * (len(sims) - 1))]:.4f}  "
              f"p50 {sims[len(sims) // 2]:.4f}  "
              f"p95 {sims[int(0.95 * (len(sims) - 1))]:.4f}")


def check(dataset: str, encoder: str, batch_size: int, cut: float,
          show: int) -> int:
    train_texts = load_texts(dataset, "train")
    if not train_texts:
        print(f"{dataset}: no train text in data/interim/; skipping")
        return 0

    train_rows = [r for r in load_jsonl(SPLITS / dataset / "train.jsonl")
                  if r["uid"] in train_texts]
    train_vecs = encode([train_texts[r["uid"]] for r in train_rows],
                        encoder, batch_size)

    findings = 0
    for split in ("dev", "test"):
        path = SPLITS / dataset / f"{split}.jsonl"
        if not path.is_file():
            continue
        texts = load_texts(dataset, split)
        rows = [r for r in load_jsonl(path) if r["uid"] in texts]
        if not rows:
            continue
        vecs = encode([texts[r["uid"]] for r in rows], encoder, batch_size)
        best, where = max_similarity(vecs, train_vecs)
        flagged = [i for i in range(len(rows)) if best[i] >= cut]
        # The number that matters is not how many this finds, it is how many it
        # finds that `make leakage` does not. SimHash fails a pair at Hamming <= 8
        # (calibrated in Phase 0), so anything above that is new information.
        new = [i for i in flagged
               if hamming(rows[i]["simhash64"], train_rows[where[i]]["simhash64"]) > 8]
        print(f"  {dataset}/{split}: {len(flagged)}/{len(rows)} rows at or above "
              f"cosine {cut} against train = {len(flagged) / len(rows):.2%}; "
              f"**{len(new)} NEW** (SimHash Hamming > 8, so invisible to make leakage)")
        findings += len(new)
        for i in sorted(flagged, key=lambda j: -best[j])[:show]:
            train_row = train_rows[where[i]]
            gap = hamming(rows[i]["simhash64"], train_row["simhash64"])
            print(f"    {best[i]:.4f}  {rows[i]['uid']} ~ {train_row['uid']}  "
                  f"(SimHash Hamming {gap}"
                  f"{', ALREADY caught by make leakage' if gap <= 8 else ', NEW'})")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_semantic_leakage.py")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--encoder", default="bge_m3")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--cut", type=float, default=DEFAULT_CUT)
    parser.add_argument("--calibrate", action="store_true",
                        help="measure the two distributions before trusting --cut")
    parser.add_argument("--pairs", type=int, default=200)
    parser.add_argument("--show", type=int, default=5)
    args = parser.parse_args(argv)
    set_all_seeds(SEED)

    if args.all:
        datasets = sorted(p.name for p in SPLITS.iterdir()
                          if p.is_dir() and (p / "train.jsonl").is_file())
    elif args.dataset:
        datasets = [args.dataset]
    else:
        parser.error("pass --dataset NAME or --all")

    total = 0
    for dataset in datasets:
        print(f"{dataset}:")
        if args.calibrate:
            calibrate(dataset, args.encoder, args.batch_size, args.pairs)
        total += check(dataset, args.encoder, args.batch_size, args.cut, args.show)

    print(f"\n{total} eval row(s) are semantic near-duplicates of a train row "
          f"that `make leakage` cannot see, at cosine >= {args.cut}.")
    print("This script REPORTS. It does not touch data/splits/ -- those are frozen "
          "and every Phase 1-4 number is scored against them. A finding here is a "
          "conversation, not a rebuild.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
