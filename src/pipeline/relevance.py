"""Does the evidence even talk about the claim? (free text, post-test Phase 7)

The served pipeline refuted "Taj Mahal Shah Jahan ne banwaya tha" at 0.72 from
ten passages none of which says who built the Taj Mahal: a disambiguation page,
fact-checks of other Taj Mahal rumours, and pages that matched only the word
"Shah". The verdict came from the stance model's claim prior; the evidence could
not overturn it because it was not about the claim.

This is the check that would have caught it: a passage *covers* the claim when
it contains at least half of the claim's content words -- in the form the user
typed or in its native-script transliteration, whichever covers more. If no
retrieved passage covers the claim, the system does not stand behind its answer
and abstains, with its leaning still shown (UI_UX.md §6).

The threshold (half) was fixed before it was run on any forward and is not tuned:
there is no labelled free-text set to tune it on. It applies to free text only;
AVeriTeC claims are ranked within their own evidence pools and their numbers
cannot move.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

COVERAGE = 0.5

# Function words in the three languages and both scripts: a claim's content is
# what is left. Lists, not a model -- this must run in CI without torch.
STOPWORDS = frozenset([
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "from", "by", "is", "are", "was", "were", "be", "been", "being", "has",
    "have", "had", "it", "its", "this", "that", "these", "those", "as", "not", "no",
    "did", "does", "do", "will", "would", "can", "could", "should", "may", "might",
    "than", "then", "there", "their", "they", "he", "she", "his", "her", "them",
    "who", "what", "hai", "hain", "tha", "thi", "the", "ne", "ki", "ka", "ke", "ko",
    "se", "mein", "me", "aur", "bhi", "ye", "yeh", "wo", "vo", "ho", "kar", "raha",
    "rahe", "rahi", "gaya", "gayi", "diya", "kiya", "kya", "nahi", "nahin", "hota",
    "hoti", "hote", "jata", "jati", "hunda", "hundi", "nu", "da", "di", "de", "te",
    "vich", "ch", "ate", "han", "si", "है", "हैं", "था", "थी", "थे", "ने", "की",
    "का", "के", "को", "से", "में", "और", "भी", "यह", "वह", "हो", "कर", "रहा", "रहे",
    "रही", "गया", "गई", "दिया", "किया", "क्या", "नहीं", "होता", "होती", "होते",
    "जाता", "जाती", "ਹੈ", "ਹਨ", "ਸੀ", "ਨੇ", "ਦੀ", "ਦਾ", "ਦੇ", "ਨੂੰ", "ਤੋਂ", "ਵਿੱਚ",
    "ਵਿਚ", "ਅਤੇ", "ਵੀ", "ਇਹ", "ਉਹ", "ਹੋ", "ਕਰ", "ਰਹੇ", "ਰਿਹਾ", "ਗਿਆ", "ਦਿੱਤਾ",
    "ਕੀਤਾ",
])


def _words(text: str) -> list[str]:
    """Whitespace tokens with punctuation stripped. Not a regex word class:
    Python's treats Devanagari and Gurmukhi vowel signs as non-letters and
    would cut ताज into त + ज."""
    out = []
    for token in text.lower().split():
        word = "".join(ch for ch in token if unicodedata.category(ch)[0] not in "PSZ")
        if word:
            out.append(word)
    return out


def content_terms(text: str) -> set[str]:
    """Lowercased words that carry the claim, without function words or numbers."""
    terms = set()
    for word in _words(text):
        if word in STOPWORDS or word.isdigit():
            continue
        if word.isascii() and len(word) < 3:
            continue
        terms.add(word)
    return terms


def coverage(claim_forms: Iterable[str], passage: str) -> float:
    """The best share of a claim form's content words found in the passage."""
    haystack = passage.lower()
    best = 0.0
    for form in claim_forms:
        terms = content_terms(form)
        if terms:
            best = max(best, sum(t in haystack for t in terms) / len(terms))
    return best


def covers_claim(claim_forms: list[str], passages: list[str],
                 threshold: float = COVERAGE) -> tuple[bool, float]:
    """(any passage covers the claim, the best coverage seen)."""
    best = max((coverage(claim_forms, p) for p in passages), default=0.0)
    return best >= threshold, best
