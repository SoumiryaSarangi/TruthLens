"""Post-test (Phase 7) fixes for the Taj Mahal failure: lexicon transliteration,
the transliterated free-text query, and the coverage check (built, rejected,
kept off). Dakshina and the models are replaced by small fixtures, so these
run in CI.
"""

from __future__ import annotations

import pytest

from pipeline.relevance import content_terms, coverage, covers_claim
from preprocess.translit import LexiconTransliterator, load_inverse_lexicon


@pytest.fixture
def dakshina(tmp_path):
    (tmp_path / "hi").mkdir()
    (tmp_path / "hi" / "hi.translit.sampled.train.tsv").write_text(
        "ताज\ttaj\t4\nशाह\tshah\t3\nजहाँ\tjahan\t3\nजहां\tjahan\t3\nशाह\tsah\t1\n",
        encoding="utf-8")
    return tmp_path


def test_the_inverse_lexicon_takes_the_most_attested_native_spelling(dakshina):
    lex = load_inverse_lexicon("hi", dakshina)
    assert lex["taj"] == "ताज" and lex["shah"] == "शाह"
    assert lex["jahan"] == min("जहाँ", "जहां")      # a tie resolves the same way every time


def test_lexicon_first_rules_for_the_rest(dakshina):
    pytest.importorskip("indic_transliteration")
    out = LexiconTransliterator(root=str(dakshina)).to_native("Taj Mahal Shah Jahan", "hi")
    words = out.split()
    assert words[0] == "ताज" and words[2] == "शाह"      # from the lexicon
    assert words[1] != "Mahal"                          # rules handled the rest
    assert LexiconTransliterator(root=str(dakshina)).to_native("hello", "en") == "hello"


def test_content_terms_keep_indic_words_whole():
    """A regex word class would cut ताज into त + ज; whitespace tokens do not."""
    assert content_terms("ताज महल शाह जहाँ ने बनवाया था") == {"ताज", "महल", "शाह", "जहाँ", "बनवाया"}
    assert content_terms("Taj Mahal ne banwaya tha") == {"taj", "mahal", "banwaya"}


def test_coverage_takes_the_better_of_the_typed_and_native_forms():
    forms = ["Taj Mahal Shah Jahan ne banwaya tha", "ताज महल शाह जहाँ ने बनवाया था"]
    assert coverage(forms, "ताजमहल हो सकता है: ताजमहल, burial monument") == pytest.approx(0.4)
    assert covers_claim(forms, ["शाहजहाँ ने ताज महल बनवाया"])[0] is True


def test_coverage_is_blind_across_languages__why_it_is_off():
    """The recorded reason the check was rejected: an English or Spanish
    fact-check that directly answers a Hindi claim scores zero."""
    hindi = ["नींबू पानी पीने से कैंसर ठीक हो जाता है"]
    assert coverage(hindi, "Hot water with lemon does not cure cancer") == 0.0


def test_the_new_keys_are_off_by_default():
    from pipeline.orchestrator import PipelineConfig

    cfg = PipelineConfig()
    assert cfg.free_text_translit_query is False and cfg.free_text_coverage is None


def test_the_served_config_runs_lexicon_transliteration_and_not_the_coverage_check():
    from pipeline.orchestrator import PipelineConfig

    cfg = PipelineConfig.load("configs/pipeline/dev.yaml")
    assert cfg.stage_args["preprocess"]["translit"] == "lexicon"
    assert cfg.free_text_translit_query is True
    assert cfg.free_text_coverage is None
