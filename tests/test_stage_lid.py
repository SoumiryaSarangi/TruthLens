"""Language identification (FR-3).

The mapping and refusal logic are tested without the model, because they are
where the bugs live. The one test that needs `lid.176` is marked and skipped
when the 131 MB binary is absent, which is always the case in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from preprocess.lid import MODEL_PATH, SUPPORTED, FastTextLID, ModelUnavailable

HAVE_MODEL = Path(MODEL_PATH).is_file()
needs_model = pytest.mark.skipif(not HAVE_MODEL, reason="lid.176.bin not downloaded")


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
