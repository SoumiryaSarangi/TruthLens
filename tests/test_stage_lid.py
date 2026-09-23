"""Language identification (FR-3).

The mapping and refusal logic are tested without the model, because they are
where the bugs live. The one test that needs `lid.176` is marked and skipped
when the 131 MB binary is absent, which is always the case in CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from preprocess.lid import (
    MODEL_PATH,
    OTHER_FLOOR,
    SUPPORTED,
    FastTextLID,
    HybridLID,
    ModelUnavailable,
    build_lid,
)
from preprocess.roman_lid import MODEL_PATH as ROMAN_MODEL

# BOTH halves matter. The weights live under gitignored data/raw/ and the
# `fasttext-wheel` package is in the ML lock, which CI does not install -- so a
# guard on the file alone passes locally and fails in CI, which is exactly what
# happened the first time.
HAVE_FASTTEXT = importlib.util.find_spec("fasttext") is not None
HAVE_MODEL = HAVE_FASTTEXT and Path(MODEL_PATH).is_file()
needs_model = pytest.mark.skipif(
    not HAVE_MODEL, reason="needs fasttext-wheel (ML lock) and lid.176.bin"
)


def test_native_script_decides_without_the_model():
    """Gurmukhi is Punjabi. That is a fact about the alphabet, not a prediction."""
    lid = FastTextLID(model_path="does/not/exist.bin")
    assert lid.identify("सरकार ने कहा") == ("hi", 1.0)
    assert lid.identify("ਸਤ ਸ੍ਰੀ ਅਕਾਲ") == ("pa", 1.0)


def test_empty_and_scriptless_input_is_other_without_the_model():
    """Digits and emoji carry no language, and must not reach the model."""
    lid = FastTextLID(model_path="does/not/exist.bin")
    assert lid.identify("") == ("other", 0.0)
    assert lid.identify("   ") == ("other", 0.0)
    assert lid.identify("12345 !!! \U0001f64f") == ("other", 0.0)


def test_missing_model_raises_rather_than_guessing():
    lid = FastTextLID(model_path="does/not/exist.bin")
    with pytest.raises(ModelUnavailable, match="download_models"):
        lid.identify("The government said this is true")


def test_supported_is_exactly_the_three_project_languages():
    assert set(SUPPORTED) == {"en", "hi", "pa"}


@needs_model
def test_english_is_identified_confidently():
    lid = FastTextLID()
    lang, score = lid.identify("The government said this is true and it was widely reported")
    assert lang == "en"
    assert score > 0.9


@needs_model
def test_an_unsupported_language_is_other_not_the_nearest_supported_one():
    """The bug this pins: scanning the top-k for a language we support.

    French is confidently French. `en` still appears further down the list, and
    a scan that returned the first *supported* label would answer "en" -- turning
    a correct refusal into a wrong answer, and then into an English verdict.
    """
    lid = FastTextLID()
    lang, _ = lid.identify("Bonjour tout le monde, comment allez-vous aujourd'hui")
    assert lang == "other"


@needs_model
def test_romanized_hindi_is_not_identified_and_that_is_the_finding():
    """Documents the measured FR-3 result rather than asserting a target.

    `lid.176` is trained on native-script web text. On romanized Hindi it either
    answers `en` or falls below the confidence floor -- it is never right. This
    test exists so that a future change which fixes it FAILS LOUDLY and gets
    written up, instead of silently improving a number nobody re-reads.
    """
    lid = FastTextLID()
    lang, _ = lid.identify("Sarkar ne kaha ki yeh sach hai aur sabko pata hona chahiye")
    assert lang != "hi", (
        "lid.176 now identifies romanized Hindi. That is a real improvement -- "
        "update docs/results.md and the FR-3 numbers rather than this assertion."
    )


# -----------------------------------------------------------------------------
# The hybrid: lid.176 in front, a char n-gram model behind (FR-3)
# -----------------------------------------------------------------------------

HAVE_SKLEARN = importlib.util.find_spec("sklearn") is not None
HAVE_BOTH = HAVE_MODEL and HAVE_SKLEARN and Path(ROMAN_MODEL).is_file()
needs_both = pytest.mark.skipif(
    not HAVE_BOTH, reason="needs lid.176, scikit-learn and a trained roman_lid"
)


def test_build_lid_rejects_an_unknown_implementation():
    with pytest.raises(ValueError, match="unknown language ID"):
        build_lid("not-a-real-lid")


def test_hybrid_decides_native_script_without_either_model():
    lid = HybridLID(model_path="does/not/exist.bin", roman_model_path="nope.joblib")
    assert lid.identify("\u0a38\u0a24 \u0a38\u0a4d\u0a30\u0a40 \u0a05\u0a15\u0a3e\u0a32") == ("pa", 1.0)


def test_other_floor_is_well_clear_of_the_romanized_noise_band():
    """lid.176 tops out around 0.27 on romanized Indic and 0.99 on real French.

    The threshold only has to separate those two, so it is not a delicate
    number -- this pins that it stays in the gap rather than drifting into it.
    """
    assert 0.35 < OTHER_FLOOR < 0.90


@needs_both
def test_hybrid_identifies_romanized_hindi_that_fasttext_cannot():
    lid = HybridLID()
    lang, _ = lid.identify("Sarkar ne kaha ki yeh sach hai aur sabko pata hona chahiye")
    assert lang == "hi"


@needs_both
def test_hybrid_identifies_romanized_punjabi():
    lid = HybridLID()
    lang, _ = lid.identify(
        "Punjab sarkar ne kisana layi nawi scheme kaddi hai, har kisan nu 6000 rupaye milange"
    )
    assert lang == "pa"


@needs_both
def test_hybrid_keeps_the_unsupported_language_refusal():
    """The reason lid.176 stays in front.

    The romanized classifier has only en/hi/pa, so on its own it would call
    French English -- and FR-3 requires an unsupported language to get an
    explicit refusal rather than a verdict in the wrong language.
    """
    lid = HybridLID()
    lang, _ = lid.identify("Bonjour tout le monde, comment allez-vous aujourd'hui")
    assert lang == "other"


@needs_both
def test_hybrid_still_gets_english_right():
    lid = HybridLID()
    assert lid.identify("The government said this is true and it was widely reported")[0] == "en"
