"""Phase 1 preprocessing: normalise whitespace, detect language and script.

Deliberately thin. Language ID is a heuristic here, not fastText, and there is
no transliteration -- both arrive in Phase 2 as separate implementations
registered alongside this one. Phase 1 is English only, so this stage's job is
to fill `Preprocessed` honestly and get out of the way.

It does NOT use `data.normalize.normalize_for_hashing`: that function is for
deduplication and strips zero-width joiners, which are meaningful in
Devanagari and Gurmukhi. Feeding its output to a model would be wrong. This is
the model-facing path and keeps the text intact.
"""

from __future__ import annotations

import re

from data.script_id import detect_script, script_purity
from pipeline.contracts import Preprocessed, Trace

_WS = re.compile(r"\s+")

# Forward artefacts stripped for processing while `original` keeps the raw text
# (FR-2). Kept short on purpose: an over-eager rule that eats real content is
# worse than one that leaves a header in.
_ARTEFACT = re.compile(
    # Longest alternative FIRST: regex alternation is left-to-right, so
    # `forwarded` would otherwise match inside "forwarded message" and leave
    # the word "message" glued to the claim.
    r"^\s*(?:forwarded\s+many\s+times|forwarded\s+message|forwarded"
    r"|sent\s+as\s+received)"
    r"\s*[:\-\u2013\u2014]?\s*",
    re.IGNORECASE,
)


class PassthroughPreprocess:
    name = "preprocess"
    impl = "passthrough"

    def run(self, trace: Trace, text: str) -> Trace:
        cleaned = text
        for _ in range(4):                      # real forwards stack the header
            cleaned, n = _ARTEFACT.subn("", cleaned)
            if not n:
                break
        cleaned = _WS.sub(" ", cleaned).strip()

        trace.pre = Preprocessed(
            original=text,
            normalized=cleaned,
            lang=self._language(cleaned),
            script=detect_script(cleaned),
            script_purity=script_purity(cleaned),
            transliterated=None,                # Phase 2
        )
        return trace

    @staticmethod
    def _language(text: str) -> str:
        """Script-derived language guess.

        Honest about what it is: a placeholder that cannot tell romanized Hindi
        from English, which is exactly the case the project cares about. That
        is Phase 2's fastText stage. Latin script reports "en" here, so a
        romanized Hindi forward is mislabelled -- known, and the reason FR-3 is
        verified in Phase 2 rather than now.
        """
        script = detect_script(text)
        if script == "deva":
            return "hi"
        if script == "guru":
            return "pa"
        return "en"
