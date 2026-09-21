"""A seeded random ranking of the claim's own pool. The retrieval floor.

The harness's registered `random_rank` baseline samples from one global pool,
which is the wrong shape here: our pools are per claim. Rather than bend the
harness, this runs through the identical batch runner and eval path a real
retriever does, and its `config_hash` becomes the `baseline:` of the BM25 run.

With ~1000 documents per claim and ~2 gold among them, Recall@10 for this
should land near 1%. If it comes out high, the pool has been filtered somewhere
and the evaluation is measuring nothing.
"""

from __future__ import annotations

import random

from retrieval.bm25 import ScoredDoc
from retrieval.kb import KnowledgeStore
from retrieval.passages import best_paragraph


class RandomRetriever:
    name = "retrieval"
    impl = "random"

    def __init__(self, split: str = "dev", k: int = 10, seed: int = 42, **_: object):
        self.store = KnowledgeStore(split)
        self.k = k
        self.seed = seed

    def topk(self, claim_text: str, claim_idx: int, k: int | None = None) -> list[ScoredDoc]:
        k = k or self.k
        pool = self.store.pool(claim_idx)
        if not pool:
            return []
        # Seeded per claim, so the ranking is reproducible and independent of
        # the order claims happen to be processed in.
        rng = random.Random(f"{self.seed}:{claim_idx}")
        picked = rng.sample(pool, k=min(k, len(pool)))
        return [ScoredDoc(d.doc_id, float(len(picked) - i), d) for i, d in enumerate(picked)]

    def best_paragraph(self, claim_text: str, doc):
        """Same paragraph selection as BM25, so the only thing that differs
        between this floor and the real retriever is the ranking itself."""
        return best_paragraph(claim_text, doc.paragraphs)
