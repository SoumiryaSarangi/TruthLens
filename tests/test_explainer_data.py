"""The explainer's training data and input format (FR-15). No weights needed."""

from __future__ import annotations

from pathlib import Path

import pytest

from common.io_jsonl import load_jsonl
from generation.indicbart import (
    LANG_TAG,
    clean_justification,
    encode_source,
    source_text,
    strip_markup,
)


def test_justifications_lose_their_references_to_the_qa_scaffolding():
    out = clean_justification("According to the QA pairs, the claim is refuted. "
                              "The 3rd Q&A shows it.")
    assert "QA" not in out and "Q&A" not in out
    assert out.startswith("The claim is refuted")


def test_source_numbers_passages_like_the_ui():
    assert source_text("C", "Refuted", ["a", "b"]) == "C </s> Refuted </s> [1] a [2] b"


class WordTokenizer:
    """One id per whitespace token, so truncation is easy to see."""

    def __init__(self):
        self.vocab: dict[str, int] = {}

    def __call__(self, text, add_special_tokens=False):
        from types import SimpleNamespace
        return SimpleNamespace(
            input_ids=[self.vocab.setdefault(w, len(self.vocab)) for w in text.split()])


def test_truncation_cuts_the_evidence_never_the_language_tag():
    tok = WordTokenizer()
    ids = encode_source(tok, "claim " + "word " * 100, max_length=10)
    assert len(ids) == 10
    assert ids[-1] == tok.vocab[LANG_TAG] and ids[-2] == tok.vocab["</s>"]


@pytest.mark.skipif(not Path("data/raw/averitec/train.json").is_file(),
                    reason="needs the AVeriTeC download")
def test_explainer_training_data_never_contains_a_test_claim():
    """The local test split is held out of train.json; iterating the file would
    train on it. Membership must come from the frozen split."""
    from generation.explain_data import examples

    train_uids = {ex["uid"] for ex in examples("train")}
    test_uids = {r["uid"] for r in load_jsonl(Path("data/splits/averitec/test.jsonl"))}
    assert train_uids and not train_uids & test_uids
    assert len(train_uids) <= 2666


def test_language_tags_and_sentence_markers_never_reach_the_user():
    assert strip_markup("<2en> The claim is refuted.</s>") == "The claim is refuted."

