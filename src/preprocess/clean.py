"""Forward-artefact stripping, shared by every preprocess implementation (FR-2).

One copy, because this is the rule that decides what text the models actually
see. Two copies would drift, and the drift would be invisible: a claim with
"message" still glued to its front retrieves and gets an NLI verdict perfectly
happily, just against slightly wrong text.

This is NOT `data.normalize.normalize_for_hashing`. That one is for
deduplication and strips zero-width joiners, which carry meaning in Devanagari
and Gurmukhi. This is the model-facing path and leaves the text intact.
"""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")

# Kept short on purpose: an over-eager rule that eats real content is worse
# than one that leaves a header in.
_ARTEFACT = re.compile(
    # Longest alternative FIRST: regex alternation is left-to-right, so
    # `forwarded` would otherwise match inside "forwarded message" and leave
    # the word "message" glued to the claim.
    r"^\s*(?:forwarded\s+many\s+times|forwarded\s+message|forwarded"
    r"|sent\s+as\s+received)"
    r"\s*[:\-\u2013\u2014]?\s*",
    re.IGNORECASE,
)

MAX_STACKED = 4


def strip_artefacts(text: str) -> str:
    """Remove stacked forward headers and collapse whitespace."""
    cleaned = text
    for _ in range(MAX_STACKED):        # real forwards stack the header
        cleaned, n = _ARTEFACT.subn("", cleaned)
        if not n:
            break
    return _WS.sub(" ", cleaned).strip()
