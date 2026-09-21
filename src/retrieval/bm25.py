"""BM25 over one claim's candidate pool. The Phase 1 retriever and the
lexical baseline every dense retriever must beat.

Index-per-claim, built and discarded. That sounds wasteful and is not: the
pool is ~1000 documents, building takes ~0.1 s from the cache, and AVeriTeC's
protocol ranks within a claim's pool anyway. A global index would answer a
different question than the benchmark asks.
"""

from __future__ import annotations

from dataclasses import dataclass

from retrieval.kb import Document, KnowledgeStore
from retrieval.passages import best_paragraph
from retrieval.tokenize import tokenize


@dataclass
class ScoredDoc:
    doc_id: str
    score: float
    document: Document


class BM25Retriever:
    name = "retrieval"
    impl = "bm25"

    def __init__(self, split: str = "dev", k: int = 10, **_: object):
        self.store = KnowledgeStore(split)
        self.k = k

    def topk(self, claim_text: str, claim_idx: int, k: int | None = None) -> list[ScoredDoc]:
        from rank_bm25 import BM25Okapi  # lazy: CI has no rank_bm25

        k = k or self.k
        pool = self.store.pool(claim_idx)
        if not pool:
            return []

        corpus = [tokenize(d.text) for d in pool]
        # A pool of empty documents would make BM25Okapi divide by zero.
        if not any(corpus):
            return []

        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(tokenize(claim_text))
        order = sorted(range(len(pool)), key=lambda i: (-scores[i], pool[i].doc_id))
        return [ScoredDoc(pool[i].doc_id, float(scores[i]), pool[i]) for i in order[:k]]

    def best_paragraph(self, claim_text: str, doc: Document) -> tuple[str, tuple[int, int]]:
        """Which paragraph the stance model reads. See retrieval/passages.py for
        why this is lexical overlap and not BM25."""
        return best_paragraph(claim_text, doc.paragraphs)
