"""Text normalisation for DEDUPLICATION AND LEAKAGE DETECTION ONLY.

=============================================================================
DO NOT FEED THE OUTPUT OF THIS MODULE TO A MODEL.
=============================================================================

`normalize_for_hashing` is deliberately destructive. It strips zero-width
joiners and non-joiners, which carry real orthographic meaning in Devanagari
and Gurmukhi, it casefolds, and it deletes emoji. That is correct for asking
"are these two rows the same claim wearing different clothes?" and badly wrong
for anything a model reads.

Model-facing preprocessing lands in src/preprocess/ during Phase 2 and is a
separate function on purpose.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width and bidi control characters. ZWJ/ZWNJ (200c/200d) are meaningful in
# Indic scripts; we remove them here so that two spellings of the same claim
# collide, which is exactly what a leakage check wants.
_INVISIBLE = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u00ad\u061c\u202a-\u202e\u2066-\u2069]"
)

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

# KNOWN DIVERGENCE from src/preprocess/passthrough.py, deliberate.
#
# The alternation below lists `forwarded` before `forwarded\s+message`, so
# "Forwarded message: X" normalises to "message: x" rather than "x". The
# model-facing copy in preprocess/passthrough.py has the longest alternative
# first and does NOT have this bug.
#
# It is not fixed here because this function computes `text_sha1` for the
# FROZEN splits. Measured: exactly 1 of 9,987 materialised texts starts with a
# forward artefact, so the fix would change one hash -- and one changed hash
# still rewrites a committed split file, invalidates SPLITS.lock, breaks the
# CI reproducibility job, and stales every results JSON built against it. A
# one-row dedup miss is not worth that.
#
# Fix it at the next legitimate split rebuild, together. tests/test_normalize_
# frozen.py pins the current behaviour so this cannot be changed by accident.
#
# WhatsApp and general forward artefacts. Extend as real forwards are collected
# in Phase 2; every addition changes text_sha1 and therefore requires a split
# rebuild, so add deliberately and record it in docs/split-changelog.md.
_FORWARD_ARTEFACTS = re.compile(
    r"^\s*(?:"
    r"forwarded(?:\s+many\s+times)?"
    r"|forwarded\s+message"
    r"|sent\s+as\s+received"
    r"|copy\s+paste[d]?"
    r"|\u0905\u0917\u094d\u0930\u0947\u0937\u093f\u0924"        # अग्रेषित (hi: forwarded)
    r"|\u0a05\u0a71\u0a17\u0a47\u0a30\u0a3f\u0a24"              # ਅੱਗੇਰਿਤ  (pa: forwarded)
    r")\s*[:\-\u2013\u2014]?\s*",
    re.IGNORECASE,
)

# Emoji, pictographs, dingbats, flags, variation selectors, skin-tone modifiers.
_EMOJI = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U0001f1e6-\U0001f1ff"
    "\u2600-\u27bf"
    "\u2b00-\u2bff"
    "\ufe0e\ufe0f"
    "\U0001f3fb-\U0001f3ff"
    "]+"
)

_WHITESPACE = re.compile(r"\s+")


def normalize_for_hashing(text: str) -> str:
    """Collapse a claim to its comparison form.

    NFKC -> drop invisibles -> strip forward artefacts -> drop URLs and emoji
    -> casefold -> collapse whitespace.
    """
    if text is None:
        raise ValueError("normalize_for_hashing received None, not a string")
    s = unicodedata.normalize("NFKC", text)
    s = _INVISIBLE.sub("", s)
    # Applied repeatedly: real forwards stack "Forwarded many times" prefixes.
    for _ in range(4):
        s, n = _FORWARD_ARTEFACTS.subn("", s)
        if not n:
            break
    s = _URL.sub(" ", s)
    s = _EMOJI.sub(" ", s)
    s = s.casefold()
    s = _WHITESPACE.sub(" ", s)
    return s.strip()


def char_shingles(text: str, k: int = 5) -> set[str]:
    """Character k-grams of the normalised text, for MinHash near-duplicate search.

    Character-level rather than word-level because the comparison has to work
    across Devanagari, Gurmukhi and Latin transliteration, where word
    boundaries are not consistent.
    """
    s = normalize_for_hashing(text)
    if len(s) < k:
        return {s} if s else set()
    return {s[i : i + k] for i in range(len(s) - k + 1)}
