"""Transliteration (FR-5).

No model and no download, so all of this runs in CI.
"""

from __future__ import annotations

import pytest

from preprocess.translit import (
    RuleBasedTransliterator,
    _prepare,
    build_transliterator,
)

DEVA_YE_SACH = "ये सच है क्या"


@pytest.fixture
def translit():
    return RuleBasedTransliterator()


def test_final_consonant_gets_the_inherent_vowel():
    """Without this, ITRANS ends the word in a dead consonant (सच् not सच)."""
    assert _prepare("sach").endswith("a")
    assert _prepare("sarkar").endswith("a")


def test_written_final_a_is_read_as_long_aa():
    """People do not type the schwa, so a final `a` they DID type is aa."""
    assert _prepare("kaha") == "kahA"
    assert _prepare("kya") == "kyA"


def test_doubled_vowels_become_long_vowels():
    assert _prepare("aam") == "Ama"
    assert _prepare("doodh") == "dUdha"


def test_romanized_hindi_becomes_devanagari(translit):
    assert translit.to_native("ye sach hai kya", "hi") == DEVA_YE_SACH


def test_romanized_punjabi_becomes_gurmukhi(translit):
    out = translit.to_native("sat sri akal ji", "pa")
    assert out != "sat sri akal ji"
    assert any("਀" <= ch <= "੿" for ch in out)


def test_english_is_left_alone(translit):
    """`en` has no native script to convert to, and mangling it would be worse."""
    assert translit.to_native("The government said this", "en") == "The government said this"
    assert translit.to_native("anything", "other") == "anything"


def test_non_letters_pass_through_untouched(translit):
    """Code-mixed forwards are full of digits, emoji and English."""
    out = translit.to_native("6000 rupaye \U0001f64f https://example.com", "hi")
    assert "6000" in out
    assert "\U0001f64f" in out


def test_empty_input_is_returned_unchanged(translit):
    assert translit.to_native("", "hi") == ""
    assert translit.to_roman("", "pa") == ""


def test_to_roman_produces_lowercase_latin(translit):
    """The synthetic romanized sets must look like something a person typed."""
    out = translit.to_roman(DEVA_YE_SACH, "hi")
    assert out == out.lower()
    assert all(ord(ch) < 128 for ch in out)


def test_medial_long_vowels_are_not_recoverable(translit):
    """Pins the documented limitation, so it is not mistaken for a bug later.

    `sarkar` is written the same whether the second vowel is short or long.
    Choosing needs a lexicon, so the rule-based path gets it wrong -- and that
    is the argument for a learned transliterator, made with a number.
    """
    assert translit.to_native("sarkar", "hi") != "सरकार"


def test_unknown_implementation_is_refused():
    with pytest.raises(ValueError, match="unknown transliterator"):
        build_transliterator("indicxlit-that-does-not-exist-yet")
