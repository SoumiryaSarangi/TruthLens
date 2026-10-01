"""The derived stance dataset (FR-10): what it inherits, what it excludes.

Synthetic AVeriTeC files and synthetic frozen splits, so this runs in CI. The
property worth the most is the first one: the local AVeriTeC test split is 307
claims HELD OUT OF train.json, so a derived row must take its parent claim's
frozen split. Recomputing splits from the file name would put test claims'
answers into stance training.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from common.io_jsonl import write_jsonl
from data import loaders
from data.labels import map_averitec_stance

ROOT = Path(__file__).resolve().parents[1]


def _claim(label, *answers, claim="The minister said X."):
    """One AVeriTeC claim whose single question carries `answers`."""
    return {"claim": claim, "label": label, "questions": [{
        "question": "Did the minister say X?",
        "answers": [{"answer": a, "answer_type": t,
                     **({"boolean_explanation": e} if e else {})}
                    for a, t, e in answers]}]}


@pytest.fixture
def raw(tmp_path, monkeypatch):
    """train.json with 4 claims, dev.json with 1, and frozen splits that hold
    train claim 2 out to TEST and drop train claim 3 entirely (as dedup would)."""
    (tmp_path / "averitec").mkdir()
    train = [
        _claim("Refuted", ("No.", "Boolean", "He never said it."),
               ("He said Y instead.", "Extractive", None), claim="Claim zero."),
        _claim("Supported", ("Yes.", "Boolean", "He did."), claim="Claim one."),
        _claim("Not Enough Evidence", ("Unclear.", "Abstractive", None),
               claim="Claim two."),
        _claim("Refuted", ("No.", "Boolean", "Never."), claim="Claim three."),
    ]
    dev = [_claim("Conflicting Evidence/Cherrypicking",
                  ("Partly.", "Abstractive", None), claim="Claim dev.")]
    (tmp_path / "averitec" / "train.json").write_text(json.dumps(train), encoding="utf-8")
    (tmp_path / "averitec" / "dev.json").write_text(json.dumps(dev), encoding="utf-8")
    monkeypatch.setattr(loaders, "RAW", tmp_path)

    splits = tmp_path / "splits"
    write_jsonl(splits / "train.jsonl", [{"source_id": "averitec:train.json:0"},
                                         {"source_id": "averitec:train.json:1"}])
    write_jsonl(splits / "test.jsonl", [{"source_id": "averitec:train.json:2"}])
    write_jsonl(splits / "dev.jsonl", [{"source_id": "averitec:dev.json:0"}])
    return splits


def _rows(splits):
    return loaders.averitec_stance_rows(splits_root=splits)


def test_a_train_json_claim_held_out_to_test_lands_in_test(raw):
    """The reason the loader reads the committed splits instead of file names."""
    out = _rows(raw)
    test_claims = {r.extra["claim"] for r in out["test"]}
    train_claims = {r.extra["claim"] for r in out["train"]}
    assert test_claims == {"Claim two."}
    assert "Claim two." not in train_claims


def test_a_claim_dropped_by_averitec_dedup_is_dropped_here(raw):
    everything = {r.extra["claim"] for rows in _rows(raw).values() for r in rows}
    assert "Claim three." not in everything


def test_conflicting_claims_are_excluded(raw):
    """Their evidence points both ways; no single stance is right per answer."""
    assert _rows(raw)["dev"] == []


def test_every_answer_inherits_its_claims_verdict(raw):
    train = _rows(raw)["train"]
    by_claim = {}
    for row in train:
        by_claim.setdefault(row.extra["claim"], set()).add(row.record["label"])
    assert by_claim == {"Claim zero.": {"Refutes"}, "Claim one.": {"Supports"}}


def test_unanswerable_is_neutral_whatever_the_verdict(tmp_path, monkeypatch):
    """Labelled with the verdict, "No answer could be found." would teach a model
    that finding nothing means Refutes."""
    (tmp_path / "averitec").mkdir()
    (tmp_path / "averitec" / "train.json").write_text(json.dumps([
        _claim("Refuted", ("No answer could be found.", "Unanswerable", None))]),
        encoding="utf-8")
    (tmp_path / "averitec" / "dev.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(loaders, "RAW", tmp_path)
    splits = tmp_path / "splits"
    write_jsonl(splits / "train.jsonl", [{"source_id": "averitec:train.json:0"}])
    write_jsonl(splits / "dev.jsonl", [])
    write_jsonl(splits / "test.jsonl", [])
    assert [r.record["label"] for r in _rows(splits)["train"]] == ["Neutral"]


def test_the_question_and_explanation_are_part_of_the_evidence(raw):
    """A Boolean answer is literally "No"; "No" to what is the whole content."""
    evidence = _rows(raw)["train"][0].extra["evidence"]
    assert evidence == "Did the minister say X? No. He never said it."


def test_duplicate_answers_within_a_claim_are_emitted_once(tmp_path, monkeypatch):
    (tmp_path / "averitec").mkdir()
    (tmp_path / "averitec" / "train.json").write_text(json.dumps([
        _claim("Refuted", ("No.", "Boolean", "x"), ("No.", "Boolean", "x"))]),
        encoding="utf-8")
    (tmp_path / "averitec" / "dev.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(loaders, "RAW", tmp_path)
    splits = tmp_path / "splits"
    write_jsonl(splits / "train.jsonl", [{"source_id": "averitec:train.json:0"}])
    write_jsonl(splits / "dev.jsonl", [])
    write_jsonl(splits / "test.jsonl", [])
    assert len(_rows(splits)["train"]) == 1


def test_the_hashed_text_is_the_pair_so_two_answers_of_one_claim_survive_dedup(raw):
    """Hashing the claim alone would let dedup keep one answer per claim and cut
    ~6.6k training rows to ~2.6k."""
    spec = importlib.util.spec_from_file_location(
        "build_splits", ROOT / "scripts" / "build_splits.py")
    build_splits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_splits)

    out = _rows(raw)
    claim_zero = [r for r in out["train"] if r.extra["claim"] == "Claim zero."]
    assert len(claim_zero) == 2
    assert len({r.record["text_sha1"] for r in claim_zero}) == 2
    kept, _ = build_splits.deduplicate(out)
    assert len([r for r in kept["train"] if r.extra["claim"] == "Claim zero."]) == 2


def test_the_interim_row_carries_both_halves(raw):
    row = _rows(raw)["train"][0]
    assert row.text == f"{row.extra['claim']}\n{row.extra['evidence']}"
    assert set(row.extra) == {"claim", "evidence", "answer_type"}


def test_a_derived_source_id_names_its_parent_claim():
    assert (loaders.stance_parent_source_id("averitec_stance:train.json:2557:q0:a1")
            == "averitec:train.json:2557")


@pytest.mark.parametrize("label, expected", [
    ("Supported", "Supports"), ("Refuted", "Refutes"),
    ("Not Enough Evidence", "Neutral"),
    ("Conflicting Evidence/Cherrypicking", None),
])
def test_label_mapping(label, expected):
    assert map_averitec_stance(label) == expected


def test_an_unknown_label_is_refused_not_guessed():
    with pytest.raises(ValueError):
        map_averitec_stance("Mostly true")


def test_missing_frozen_splits_refuse(tmp_path):
    with pytest.raises(FileNotFoundError, match="inherits"):
        loaders.averitec_split_membership(tmp_path / "nowhere")
