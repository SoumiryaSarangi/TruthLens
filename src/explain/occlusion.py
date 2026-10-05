"""Word influence by occlusion: pure helpers, no model.

docs/word-highlight-protocol.md fixes the method. A word's influence is how much the models'
probability of the SHOWN verdict falls when that word is removed from the claim; the top words are the
ones whose removal hurts most. Nothing here scores anything: `explain.words` calls the NLI models and
passes the probabilities back through these functions, so each step can be tested without a model.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

TOP_K = 3
MAX_SOURCE_SENTENCES = 2
_SENTENCE = re.compile(r"(?<=[.!?।])\s+|\n+")


def split_words(text: str) -> list[str]:
    """Whitespace tokens, the unit the reader sees marked."""
    return (text or "").split()


def without(words: Sequence[str], drop: Sequence[int]) -> str:
    """The text with the words at these positions removed."""
    gone = set(drop)
    return " ".join(w for i, w in enumerate(words) if i not in gone)


def influences(p_full: float, p_without: Sequence[float]) -> list[float]:
    """Drop in the verdict's probability when each word is removed (positive: the word pushed toward it)."""
    return [p_full - p for p in p_without]


def top_indices(influence: Sequence[float], k: int = TOP_K) -> list[int]:
    """The k words that pushed hardest toward the verdict, in reading order.

    Only a word whose removal lowers the probability counts, so a claim where nothing mattered gets
    no highlight rather than a made-up one. Ties go to the earlier word.
    """
    ranked = sorted((i for i, v in enumerate(influence) if v > 0), key=lambda i: (-influence[i], i))
    return sorted(ranked[:k])


def bottom_indices(influence: Sequence[float], k: int = TOP_K) -> list[int]:
    """The k words whose removal helps the verdict most or hurts least (the control in the protocol)."""
    return sorted(sorted(range(len(influence)), key=lambda i: (influence[i], i))[:k])


def source_sentences(premise: str, limit: int = MAX_SOURCE_SENTENCES) -> list[str]:
    """The sentences of the judged premise (it is already the two closest to the claim)."""
    return [s.strip() for s in _SENTENCE.split(premise or "") if s.strip()][:limit]
