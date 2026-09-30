"""Warm the passage-vector cache for hybrid retrieval (FR-9).

    python scripts/build_dense_cache.py --split-file data/splits/averitec/dev.jsonl --depth 500

Encodes BM25's top `--depth` documents for every claim in a split, passage by
passage, into `data/interim/dense_cache/`. Run it once at the deepest depth the
ablation needs and every shallower depth and every fusion rule afterwards is a
read: the cache is keyed by document, not by depth.

It goes through `HybridRetriever.warm`, the same code the evaluation and the API
use, so the vectors cached here are exactly the ones they would have computed.

Measured cost on real knowledge-store documents: 103 passages/s at 256 tokens,
~3 passages per document, so N=500 over the 500 dev claims is ~2 hours. Resumable
-- one file per claim, written atomically -- so an interruption costs one claim.
One GPU job at a time on this machine: Phase 4 took free RAM to 0.74 GB running
two, and both crawled.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import set_all_seeds  # noqa: E402
from retrieval.hybrid import HybridRetriever  # noqa: E402
from retrieval.kb import claim_index_from_uid, kb_split_from_source_id  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/build_dense_cache.py")
    ap.add_argument("--split-file", required=True)
    ap.add_argument("--depth", type=int, default=500)
    ap.add_argument("--chunk-chars", type=int, default=1000)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    set_all_seeds()

    split_path = Path(args.split_file)
    rows = list(load_jsonl(split_path))
    if args.limit:
        rows = rows[: args.limit]
    stores = {kb_split_from_source_id(r["source_id"]) for r in rows}
    if len(stores) != 1:
        print(f"REFUSED: {split_path} mixes knowledge stores {sorted(stores)}")
        return 2
    kb_split = stores.pop()
    texts = {r["uid"]: r["text"]
             for r in load_jsonl(Path("data/interim") / split_path.parent.name
                                 / f"{split_path.stem}.jsonl")}

    retriever = HybridRetriever(split=kb_split, k=min(10, args.depth),
                                depth=args.depth, chunk_chars=args.chunk_chars,
                                batch_size=args.batch_size, cache="readwrite")
    print(f"{len(rows)} claims from the {kb_split} knowledge store, depth "
          f"{args.depth} -> {retriever._cache.dir}")

    started = time.time()
    encoded = 0
    for n, row in enumerate(rows, start=1):
        encoded += retriever.warm(texts[row["uid"]],
                                  claim_index_from_uid(row["source_id"]))
        if n % 10 == 0 or n == len(rows):
            elapsed = time.time() - started
            rate = n / max(elapsed, 1e-6)
            print(f"  {n:4}/{len(rows)}  {encoded:7} passages  "
                  f"{encoded / max(elapsed, 1e-6):5.0f}/s  "
                  f"eta {(len(rows) - n) / max(rate, 1e-6) / 60:5.1f} min", flush=True)

    print(f"\n  {encoded} passages encoded in {(time.time() - started) / 60:.1f} min "
          "(already-cached documents cost nothing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
