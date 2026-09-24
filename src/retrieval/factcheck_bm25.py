"""BM25 over the global fact-check pool. The lexical floor for claim matching.

`src/retrieval/CLAUDE.md`: *"BM25 is the real baseline. A dense retriever that
does not beat BM25 on a language is a finding to report, not a bug to hide."*

Distinct from `retrieval/bm25.py`, which indexes ONE AVeriTeC claim's candidate
pool and discards it. This one is global and persistent, because claim matching
searches every fact-check for every post -- there is no per-query pool.

Two properties that matter downstream:

* **Its scores are unbounded.** Every other retriever here returns a cosine in
  [-1, 1]. A `tau_match` chosen against cosines accepts everything from this
  one, and a τ chosen here accepts nothing from the others. `task: fast_path`
  warns when τ turns out to be on the wrong scale, and this retriever is why
  that warning exists.
* **BM25 is corpus-dependent.** IDF is a function of what else is indexed, so
  the withheld-answer negatives that `task: fast_path` derives are exact for a
  cosine scorer and only approximate here. Stated in the config notes.

`rank_bm25` is imported lazily: CI installs the core lock and does not have it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common.io_jsonl import load_jsonl

INDEX_DIR = Path("data/interim/index")
CORPUS = "bm25_corpus.jsonl"


@dataclass
class ScoredDoc:
    doc_id: str
    score: float
    document: object = None


class FactCheckBM25Retriever:
    """Global lexical retrieval over the MultiClaim fact-check pool."""

    name = "retrieval"
    impl = "bm25_factcheck"

    def __init__(self, k: int = 10, index_dir: str | Path | None = None,
                 **_: object) -> None:
        self.k = k
        self.index_dir = Path(index_dir) if index_dir else INDEX_DIR
        self._ids: list[str] | None = None
        self._bm25 = None

    def _load(self):
        """Build the index from the tokenized corpus, once.

        Rebuilt from tokens rather than unpickled: seconds to build, and one
        artefact to keep in step with the pool instead of two.
        """
        if self._bm25 is None:
            from rank_bm25 import BM25Okapi

            path = self.index_dir / CORPUS
            if not path.is_file():
                raise RuntimeError(
                    f"no lexical index at {path}. Run "
                    "`python scripts/build_factcheck_bm25.py`."
                )
            rows = list(load_jsonl(path))
            self._ids = [r["id"] for r in rows]
            self._bm25 = BM25Okapi([r["tokens"] for r in rows])
        return self._ids, self._bm25

    def rank_batch(self, queries: list[str], k: int | None = None) -> list[list[ScoredDoc]]:
        """Best-first ranking per query. Scores are BM25, not similarities.

        The top-k selection is `argpartition`, not a full sort. Sorting all
        78,077 rows per query with a Python key function is ~1-2 s each, which is
        50-100 minutes over a 3,153-row split -- measured the slow way once.
        Partitioning is O(n) and sorts only the k survivors.
        """
        import numpy as np

        from retrieval.tokenize import tokenize

        ids, bm25 = self._load()
        k = k or self.k
        out: list[list[ScoredDoc]] = []
        for query in queries:
            tokens = tokenize(query)
            if not tokens:
                # A query with no lexical content cannot be scored, and a list of
                # zeros ranked by id would be a silent arbitrary ranking.
                out.append([])
                continue
            scores = np.asarray(bm25.get_scores(tokens), dtype=np.float32)
            take = min(k, scores.shape[0])
            top = np.argpartition(-scores, kth=take - 1)[:take]
            top = top[np.argsort(-scores[top], kind="stable")]
            out.append([ScoredDoc(ids[i], float(scores[i])) for i in top])
        return out

    def topk(self, claim_text: str, claim_idx: int | None = None,
             k: int | None = None) -> list[ScoredDoc]:
        """`claim_idx` is accepted and ignored: the pool here is global.

        The signature matches `BM25Retriever.topk` so the two are
        interchangeable through the registry.
        """
        return self.rank_batch([claim_text], k=k)[0]
