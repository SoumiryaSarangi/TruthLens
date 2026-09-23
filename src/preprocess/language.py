"""Phase 2 preprocessing: the language layer (FR-2, FR-3, FR-4, FR-5).

Replaces the Phase 1 heuristic that read Latin script as English and therefore
never transliterated anything -- which is to say, it replaces the reason Phase 1
could not handle the input this project exists for.

    strip artefacts -> language ID -> script + purity -> transliterate

`SYSTEM_DESIGN.md` 6 draws those as three stages. They are one here because the
pipeline defines one `preprocess` stage writing one `Preprocessed` object, and
the composition inside it is an implementation detail. Widening `registry.STAGES`
would change every config and every golden trace to express the same thing.

Transliteration is deliberately ADDITIVE: `normalized` keeps the text the user
actually typed and the native-script version goes in `transliterated`, so a
downstream stage can use either and the UI can show both (`UI_UX.md` 4). A
transliterator that overwrote the original would make its own errors invisible.
"""

from __future__ import annotations

from data.script_id import detect_script, script_purity
from pipeline.contracts import Preprocessed, Trace
from preprocess.clean import strip_artefacts
from preprocess.lid import DEFAULT_FLOOR, FastTextLID
from preprocess.translit import build_transliterator

# Scripts that already ARE the native script for their language. A row in
# Devanagari needs no transliteration; only Latin-script hi/pa does.
NATIVE_SCRIPT = {"hi": "deva", "pa": "guru"}


class LanguagePreprocess:
    """fastText language ID plus transliteration of romanized hi/pa."""

    name = "preprocess"
    impl = "full"

    def __init__(self, translit: str = "rulebased", lid_floor: float = DEFAULT_FLOOR,
                 model_path: str | None = None, force_lang: str | None = None) -> None:
        self.lid = FastTextLID(model_path=model_path, floor=lid_floor)
        self.translit_impl = translit
        self._translit = None
        # Skip language ID and assert the answer. Two uses, both legitimate:
        # measuring the transliterator on its own, separately from the language
        # ID that feeds it -- without this, FR-5's number is really FR-3's --
        # and serving a user who has told the UI what language they are writing.
        # Never a default: a forced language that is wrong is silent.
        self.force_lang = force_lang

    def _transliterator(self):
        if self._translit is None:
            self._translit = build_transliterator(self.translit_impl)
        return self._translit

    def run(self, trace: Trace, text: str) -> Trace:
        cleaned = strip_artefacts(text)
        script = detect_script(cleaned)

        if self.force_lang:
            lang, confidence = self.force_lang, 1.0
        else:
            try:
                lang, confidence = self.lid.identify(cleaned)
            except Exception as exc:
                # Falling back to the script reading is strictly better than
                # refusing: Devanagari is still Hindi without fastText. Recorded,
                # because a silent fallback would make the FR-3 number a lie.
                trace.record(self.name, self.impl, 0.0,
                             f"degraded: language ID unavailable ({type(exc).__name__}); "
                             f"falling back to script")
                lang = {"deva": "hi", "guru": "pa"}.get(script, "en")
                confidence = 0.0

        transliterated = None
        if lang in NATIVE_SCRIPT and script != NATIVE_SCRIPT[lang]:
            try:
                candidate = self._transliterator().to_native(cleaned, lang)
                # A transliterator that returns its input has not failed loudly,
                # it has failed silently -- treat that as no transliteration
                # rather than claim one happened.
                transliterated = candidate if candidate != cleaned else None
            except Exception as exc:
                trace.record(self.name, self.impl, 0.0,
                             f"degraded: no transliteration ({type(exc).__name__})")

        trace.pre = Preprocessed(
            original=text,
            normalized=cleaned,
            lang=lang,
            script=script,
            script_purity=script_purity(cleaned),
            transliterated=transliterated,
        )
        trace.record(self.name, self.impl, 0.0,
                     f"lang={lang} p={confidence:.2f} script={script}"
                     + ("" if transliterated is None else " transliterated"))
        return trace
