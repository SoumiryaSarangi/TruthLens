"""Choosing which paragraph of a document the stance model reads.

Deliberately NOT BM25. BM25's IDF is computed across a corpus, and a single
document has only a handful of paragraphs -- with two, `rank_bm25` returns
idf = 0 for every term (log(1.5) - log(1.5)), every score comes out 0.0, and
`max()` silently selects the first paragraph no matter what it says. That
failure is invisible: the pipeline still returns a verdict, just one formed
from the wrong text.

So paragraph selection uses plain lexical overlap, which degrades gracefully at
any size. It is a weak scorer and is meant to be: Phase 5 replaces it with a
dense passage ranker, and this is the floor that has to be beaten.
"""

from __future__ import annotations

import math

from retrieval.tokenize import tokenize


def score_paragraph(query_terms: set[str], paragraph: str) -> float:
    """Distinct query-term coverage, damped by paragraph length.

    Coverage rather than raw count so one repeated word cannot outrank a
    paragraph that matches the whole query; sqrt length damping so a very long
    paragraph does not win merely by containing everything.
    """
    tokens = tokenize(paragraph)
    if not tokens or not query_terms:
        return 0.0
    hits = query_terms & set(tokens)
    if not hits:
        return 0.0
    return len(hits) / math.sqrt(len(tokens))


def best_paragraph(claim_text: str, paragraphs) -> tuple[str, tuple[int, int]]:
    """Return the most claim-relevant paragraph and its offsets in the joined text.

    Offsets are into `" ".join(paragraphs)` -- the same joining `Document.text`
    uses -- so the UI can highlight the span that was actually judged rather
    than an arbitrary prefix.
    """
    paras = [p for p in paragraphs if p and p.strip()]
    if not paras:
        return "", (0, 0)

    query = set(tokenize(claim_text))
    scores = [score_paragraph(query, p) for p in paras]
    best = max(range(len(paras)), key=lambda i: (scores[i], -i))

    start = sum(len(p) + 1 for p in paras[:best])
    return paras[best], (start, start + len(paras[best]))
