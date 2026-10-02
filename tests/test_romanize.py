"""The romanizer that builds x_claim_romanized (FR-26).

What matters most is the token contract: one whitespace token in, one
non-empty token out, never a space inside. X-CLAIM's span gold is indexed by
token, so a romanizer that merged or split a single token would shift every
gold tag after it while every number still looked plausible.
"""

from __future__ import annotations

import pytest

from preprocess.romanize import load_lexicon, romanize, romanize_token, rule_romanize

NO_LEXICON: dict = {}


@pytest.mark.parametrize("native, roman", [
    ("करना", "karna"),          # medial schwa deleted (VC_CV), final aa shortened
    ("समझना", "samajhna"),
    ("नरेंद्र", "narendra"),     # final schwa KEPT after a conjunct
    ("मंत्र", "mantra"),
    ("किसान", "kisaan"),
    ("ਇੱਕ", "ikk"),              # addak doubles the next consonant
    ("ਪ੍ਰਧਾਨ", "pradhaan"),       # subjoined consonant through the virama
    ("ज़मीन", "zameen"),          # nukta
])
def test_rules(native, roman):
    assert rule_romanize(native) == roman


def test_one_token_in_one_token_out():
    text = "क्या यह सच है कि सरकार हर छात्र को 6000 रुपये देगी? ਲਾਹੌਰ, ਪੰਜਾਬ। COVID-19"
    out = romanize(text, NO_LEXICON).split()
    assert len(out) == len(text.split())
    assert all(token for token in out)


def test_punctuation_digits_and_latin_survive():
    assert romanize_token("ਪੰਜਾਬ।", NO_LEXICON).endswith(".")
    assert romanize_token("(भारत)", NO_LEXICON).startswith("(")
    assert romanize_token("२०२०", NO_LEXICON) == "2020"
    assert romanize_token("WHO", NO_LEXICON) == "WHO"


def test_lexicon_beats_rules_and_is_chosen_by_script():
    lexicons = {"deva": {"दिल्ली": "delhi"}, "guru": {"ਲਾਹੌਰ": "lahore"}}
    assert romanize_token("दिल्ली", lexicons) == "delhi"
    assert romanize_token("ਲਾਹੌਰ!", lexicons) == "lahore!"
    assert romanize_token("दिल्ली", NO_LEXICON) == "dilli"      # the rule fallback


def test_lexicon_takes_the_most_attested_spelling(tmp_path):
    (tmp_path / "pa").mkdir()
    (tmp_path / "pa" / "pa.translit.sampled.train.tsv").write_text(
        "ਪੰਜਾਬ\tpanjab\t1\nਪੰਜਾਬ\tpunjab\t3\nਘਰ\tghar\t2\nਘਰ\tghr\t2\n",
        encoding="utf-8")
    lex = load_lexicon("pa", root=tmp_path)
    assert lex["ਪੰਜਾਬ"] == "punjab"
    assert lex["ਘਰ"] == "ghr"           # tie on count -> shorter wins, deterministic


def test_a_missing_lexicon_is_empty_not_an_error(tmp_path):
    assert load_lexicon("hi", root=tmp_path) == {}
