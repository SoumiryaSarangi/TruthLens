"""Encode the MultiClaim fact-check pool for claim matching (Phase 2).

    python scripts/build_factcheck_index.py --encoder bge_m3
    python scripts/build_factcheck_index.py --encoder all

Writes data/interim/index/{encoder}.npy plus a shared ids.json, both gitignored:
they are derived from restricted MultiClaim text and must not be redistributed.

## The pool is 78,077, and that is a reported parameter

Every fact-check that appears in at least one annotated pair. Not the 3,943 the
dev queries actually point at -- retrieving from only the documents that happen
to be answers is not retrieval, and it would inflate every number on the ladder.
Not all 435,252 either, which is ~5.5x the encoding cost for a harder task than
the MultiClaim / SemEval-2025 Task 7 setup the published numbers use.

The size is written into the index metadata and into every results JSON, the
same way Phase 1 reported its 4000-character knowledge-store truncation, because
a retrieval score without its corpus size is not comparable to anything.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import write_json  # noqa: E402
from common.seeds import set_all_seeds  # noqa: E402
from data.multiclaim import load_fact_checks, load_pairs  # noqa: E402
from retrieval.encoders import LADDER, build_encoder  # noqa: E402

OUT = Path("data/interim/index")


def fact_check_text(fc) -> str:
    """Claim plus title, which is what a post is actually matched against.

    The claim alone is often a bare sentence fragment; the title carries the
    subject. Concatenating is the standard MultiClaim setup.
    """
    parts = [p for p in (fc.claim, fc.title) if p]
    return " ".join(parts).strip()


def load_pool() -> tuple[list[str], list[str]]:
    """(ids, texts) for every fact-check in at least one annotated pair."""
    wanted = {fc_id for _, fc_id, _ in load_pairs()}
    fact_checks = load_fact_checks(ids=wanted)
    ids, texts = [], []
    for fc_id in sorted(wanted):
        fc = fact_checks.get(fc_id)
        if fc is None:
            continue
        text = fact_check_text(fc)
        if text:
            ids.append(fc_id)
            texts.append(text)
    return ids, texts


def build(encoder_name: str, ids: list[str], texts: list[str], batch_size: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{encoder_name}.npy"
    if dest.is_file():
        existing = np.load(dest, mmap_mode="r")
        if existing.shape[0] == len(ids):
            print(f"  have   {dest.name}  {existing.shape}")
            return
        print(f"  {dest.name} has {existing.shape[0]} rows but the pool has "
              f"{len(ids)}; rebuilding")

    encoder = build_encoder(encoder_name)
    started = time.time()
    encoder.fit(texts)          # no-op for the neural rungs
    fitted = time.time()
    if fitted - started > 1:
        print(f"    fit in {(fitted - started) / 60:.1f} min")

    chunks: list[np.ndarray] = []
    step = max(batch_size * 64, 2048)
    for start in range(0, len(texts), step):
        chunks.append(encoder.encode(texts[start:start + step], batch_size=batch_size))
        done = min(start + step, len(texts))
        rate = done / max(time.time() - fitted, 1e-6)
        print(f"    {done:6d}/{len(texts)}  {rate:6.0f} docs/s  "
              f"eta {(len(texts) - done) / max(rate, 1e-6) / 60:5.1f} min", flush=True)

    matrix = np.vstack(chunks).astype(np.float16)
    np.save(dest, matrix)

    # TF-IDF is FITTED STATE, not weights. Refitting it at query time would mean
    # re-reading a 493 MB CSV and redoing the SVD on every run -- and, worse, any
    # drift in the corpus would silently put queries in a different vector space
    # from the documents. Save it with the index it belongs to.
    if encoder_name == "tfidf":
        import joblib

        state = OUT / "tfidf.state.joblib"
        joblib.dump({"vectorizer": encoder._vectorizer, "svd": encoder._svd},
                    state, compress=3)
        print(f"  wrote {state}  {state.stat().st_size / 1e6:.0f} MB")
    print(f"  wrote {dest}  {matrix.shape}  {dest.stat().st_size / 1e6:.0f} MB "
          f"in {(time.time() - fitted) / 60:.1f} min")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_factcheck_index.py")
    parser.add_argument("--encoder", default="all",
                        help=f"one of {LADDER}, or 'all'")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)
    set_all_seeds()

    print("loading the fact-check pool")
    ids, texts = load_pool()
    print(f"  {len(ids)} fact-checks in at least one annotated pair")

    ids_path = OUT / "ids.json"
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(ids_path, {"n": len(ids), "ids": ids,
                          "pool": "fact-checks appearing in >=1 annotated pair"})

    names = LADDER if args.encoder == "all" else (args.encoder,)
    for name in names:
        print(f"{name}:")
        build(name, ids, texts, args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
