"""Tokenize the MultiClaim fact-check pool for lexical matching (Phase 4).

    python scripts/build_factcheck_bm25.py

Writes `data/interim/index/bm25_corpus.jsonl`, gitignored like every other
index artefact: it is derived from restricted MultiClaim text.

## Why a lexical index at all, when BGE-M3 exists

`src/retrieval/CLAUDE.md`: *"BM25 is the real baseline. A dense retriever that
does not beat BM25 on a language is a finding to report, not a bug to hide."*
Phase 2's ladder used TF-IDF as its lexical rung, which is a reasonable stand-in
and is not the thing that sentence says. `SYSTEM_DESIGN.md` §7 budgets a
`factcheck.bm25.pkl` alongside the dense index for exactly this.

It is also the only retriever in the project whose scores are **unbounded**,
which makes it the honest test of whether `task: fast_path`'s τ machinery
survives a change of scale. A τ chosen on cosines accepts everything here.

## What is stored, and what is not

The tokenized corpus, not a pickled `BM25Okapi`. Rebuilding the index from
tokens takes seconds; a pickled rank_bm25 object is large, version-fragile, and
would be a second thing to keep in step with the corpus. The id ORDER matches
`ids.json` exactly, so a row index means the same thing in both indexes.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, write_jsonl  # noqa: E402
from common.seeds import set_all_seeds  # noqa: E402
from retrieval.tokenize import tokenize  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from build_factcheck_index import load_pool  # noqa: E402

OUT = Path("data/interim/index")
CORPUS = OUT / "bm25_corpus.jsonl"
IDS = OUT / "ids.json"


def build(force: bool = False) -> int:
    if CORPUS.is_file() and not force:
        print(f"{CORPUS} exists; --force to rebuild")
        return 0

    set_all_seeds()
    started = time.time()
    ids, texts = load_pool()
    print(f"  pool: {len(ids)} fact-checks in >=1 annotated pair")

    # The dense index must already exist, because the two have to agree about
    # what row `i` is. A lexical run and a dense run that disagree about the
    # corpus are not comparable, and the difference would look like a result.
    if IDS.is_file():
        existing = load_json(IDS)["ids"]
        if existing != ids:
            print(f"  REFUSING: {IDS} lists {len(existing)} ids and this pool has "
                  f"{len(ids)}. The dense and lexical indexes would be over "
                  "different corpora, and their scores would not be comparable. "
                  "Rebuild both from the same sources.")
            return 2

    empty = 0
    rows = []
    for fc_id, text in zip(ids, texts, strict=True):
        tokens = tokenize(text)
        if not tokens:
            empty += 1
            continue
        rows.append({"id": fc_id, "tokens": tokens})

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(CORPUS, rows)
    lengths = [len(r["tokens"]) for r in rows]
    print(f"wrote {CORPUS}  n={len(rows)} in {time.time() - started:.1f}s")
    print(f"  tokens per document: mean {sum(lengths) / len(lengths):.1f}, "
          f"min {min(lengths)}, max {max(lengths)}")
    if empty:
        print(f"  {empty} fact-check(s) tokenized to nothing and were dropped")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_factcheck_bm25.py")
    parser.add_argument("--force", action="store_true", help="rebuild if it exists")
    args = parser.parse_args(argv)
    return build(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
