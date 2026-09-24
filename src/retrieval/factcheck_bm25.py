"""BM25 over the global fact-check pool. The lexical floor for claim matching.

`src/retrieval/CLAUDE.md`: *"BM25 is the real baseline. A dense retriever that
does not beat BM25 on a language is a finding to report, not a bug to hide."*

Distinct from `retrieval/bm25.py`, which indexes ONE AVeriTeC claim's candidate
pool and discards it. This one is global and persistent, because claim matching
searches every fact-check for every post -- there is no per-query pool.

## Why this does not use `rank_bm25`, measured

`rank_bm25.BM25Okapi` scores a query by looping **in Python over all 78,077
documents once per query term**: `np.array([doc.get(q) or 0 for doc in
self.doc_freqs])`. Measured on this pool, that is ~1.07 s per query -- and
MultiClaim dev posts average 59.8 tokens with a p99 of 542, so the tail is
brutal. A 3,153-row split took over an hour and its ~1.5 GB of per-document
dicts got paged out on a 16 GB machine, after which it crawled.

Okapi BM25 ignores query-term weighting, so **every (document, term) weight is
query-independent and precomputes**. The whole index becomes one sparse matrix:

    W[d, t] = idf[t] * f(t,d) * (k1 + 1) / (f(t,d) + k1 * (1 - b + b * dl_d / avgdl))

and a query is `W @ v`, where `v` counts the query's terms. That is ~20 MB of
CSR and a few milliseconds per query instead of a second.

The arithmetic is `BM25Okapi`'s exactly, including its negative-IDF floor, so the
numbers stay comparable with `retrieval/bm25.py` on the AVeriTeC side.
`tests/test_stage_retrieval.py` checks it against `rank_bm25` as an independent
oracle rather than against itself.

## Two properties that matter downstream

* **Its scores are unbounded.** Every other retriever here returns a cosine in
  [-1, 1]. A `tau_match` chosen against cosines accepts everything from this
  one, and a tau chosen here accepts nothing from the others. `task: fast_path`
  warns when tau turns out to be on the wrong scale, and this retriever is why
  that warning exists.
* **BM25 is corpus-dependent.** IDF is a function of what else is indexed, so
  the withheld-answer negatives `task: fast_path` derives are exact for a cosine
  scorer and only approximate here. Stated in the config notes.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from common.io_jsonl import load_jsonl

INDEX_DIR = Path("data/interim/index")
CORPUS = "bm25_corpus.jsonl"

# BM25Okapi's defaults, named here so the two BM25s in this project agree.
K1 = 1.5
B = 0.75
# rank_bm25 replaces a negative IDF (a term in more than half the corpus) with
# this fraction of the average IDF, rather than letting it push scores down.
EPSILON = 0.25


@dataclass
class ScoredDoc:
    doc_id: str
    score: float
    document: object = None


def build_weights(corpus: list[list[str]]) -> tuple:
    """(csr_matrix, vocab) of precomputed BM25 term weights.

    Returns the weight matrix W with one row per document and one column per
    vocabulary term. Nothing here depends on a query.
    """
    from scipy.sparse import csr_matrix

    n_docs = len(corpus)
    lengths = np.array([len(doc) for doc in corpus], dtype=np.float64)
    avgdl = lengths.mean() if n_docs else 0.0

    vocab: dict[str, int] = {}
    doc_freq: Counter = Counter()
    counted: list[Counter] = []
    for tokens in corpus:
        freqs = Counter(tokens)
        counted.append(freqs)
        for term in freqs:
            if term not in vocab:
                vocab[term] = len(vocab)
            doc_freq[term] += 1

    idf = np.empty(len(vocab), dtype=np.float64)
    negatives = []
    for term, col in vocab.items():
        df = doc_freq[term]
        value = math.log(n_docs - df + 0.5) - math.log(df + 0.5)
        idf[col] = value
        if value < 0:
            negatives.append(col)
    if len(vocab):
        average_idf = float(idf.mean())
        # BM25Okapi's floor: a term in most of the corpus would otherwise
        # subtract from every score it appears in.
        for col in negatives:
            idf[col] = EPSILON * average_idf

    # norm[d] depends only on the document's length.
    norm = K1 * (1 - B + B * lengths / avgdl) if avgdl else np.zeros(n_docs)

    rows, cols, data = [], [], []
    for d, freqs in enumerate(counted):
        for term, f in freqs.items():
            col = vocab[term]
            rows.append(d)
            cols.append(col)
            data.append(idf[col] * f * (K1 + 1) / (f + norm[d]))
    weights = csr_matrix(
        (np.asarray(data, dtype=np.float32),
         (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32))),
        shape=(n_docs, max(len(vocab), 1)),
    )
    return weights, vocab


class FactCheckBM25Retriever:
    """Global lexical retrieval over the MultiClaim fact-check pool."""

    name = "retrieval"
    impl = "bm25_factcheck"

    def __init__(self, k: int = 10, index_dir: str | Path | None = None,
                 **_: object) -> None:
        self.k = k
        self.index_dir = Path(index_dir) if index_dir else INDEX_DIR
        self._ids: list[str] | None = None
        self._weights = None
        self._vocab: dict[str, int] | None = None

    def _load(self):
        """Build the weight matrix from the tokenized corpus, once.

        Built rather than unpickled: ~20 MB and a few seconds from tokens, versus
        a large, version-fragile pickle that would be a second artefact to keep
        in step with the pool.
        """
        if self._weights is None:
            path = self.index_dir / CORPUS
            if not path.is_file():
                raise RuntimeError(
                    f"no lexical index at {path}. Run "
                    "`python scripts/build_factcheck_bm25.py`."
                )
            rows = list(load_jsonl(path))
            self._ids = [r["id"] for r in rows]
            self._weights, self._vocab = build_weights([r["tokens"] for r in rows])
        return self._ids, self._weights, self._vocab

    def scores(self, tokens: list[str]) -> np.ndarray:
        """BM25 score of every document for one tokenized query."""
        _, weights, vocab = self._load()
        query = np.zeros(weights.shape[1], dtype=np.float32)
        hits = 0
        for term in tokens:
            col = vocab.get(term)
            if col is not None:
                # Counted, not set: a repeated query term counts twice, which is
                # what looping over the token list does in BM25Okapi.
                query[col] += 1.0
                hits += 1
        if not hits:
            return np.zeros(weights.shape[0], dtype=np.float32)
        return weights @ query

    def rank_batch(self, queries: list[str], k: int | None = None) -> list[list[ScoredDoc]]:
        """Best-first ranking per query. Scores are BM25, not similarities."""
        from retrieval.tokenize import tokenize

        ids, _, _ = self._load()
        k = k or self.k
        out: list[list[ScoredDoc]] = []
        for query in queries:
            tokens = tokenize(query)
            if not tokens:
                # A query with no lexical content cannot be scored, and a list of
                # zeros ranked by id would be a silent arbitrary ranking.
                out.append([])
                continue
            scores = self.scores(tokens)
            take = min(k, scores.shape[0])
            # argpartition, not a full sort: sorting 78,077 rows per query with a
            # Python key was the first version and cost ~1.5 s each.
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
