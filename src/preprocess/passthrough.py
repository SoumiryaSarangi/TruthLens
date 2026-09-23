"""Phase 1 preprocessing: normalise whitespace, detect language and script.

Deliberately thin. Language ID is a heuristic here, not fastText, and there is
no transliteration -- both arrive in Phase 2 as separate implementations
registered alongside this one. Phase 1 is English only, so this stage's job is
to fill `Preprocessed` honestly and get out of the way.

Forward-artefact stripping (FR-2) lives in `preprocess.clean` so this and the
Phase 2 implementation share exactly one copy of it.
"""

from __future__ import annotations

from data.script_id import detect_script, script_purity
from pipeline.contracts import Preprocessed, Trace
from preprocess.clean import strip_artefacts


class PassthroughPreprocess:
    name = "preprocess"
    impl = "passthrough"

    def run(self, trace: Trace, text: str) -> Trace:
        cleaned = strip_artefacts(text)

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
