"""Stance stage tests.

The mapping from NLI labels to stance is the whole of the modelling here, and
getting it backwards would invert every verdict while everything still ran and
produced plausible numbers. So it is asserted directly, and the real model is
exercised separately behind the `gpu` marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from stance.baseline import AlwaysNeutralStance
from stance.nli import NLI_TO_STANCE, NLIStance


def test_nli_label_mapping_is_the_intended_one():
    assert NLI_TO_STANCE == {
        "entailment": "Supports",
        "contradiction": "Refutes",
        "neutral": "Neutral",
    }


def test_mapping_targets_are_valid_stance_labels():
    from data.labels import STANCE_3CLASS

    assert set(NLI_TO_STANCE.values()) == set(STANCE_3CLASS)


def test_importing_the_nli_stage_does_not_load_a_model():
    """Constructing must stay free; CI imports this module with no torch."""
    stage = NLIStance()
    assert not stage.loaded


def test_always_neutral_baseline_is_neutral_for_everything():
    stage = AlwaysNeutralStance()
    out = stage.label("a claim", ["passage one", "passage two"])
    assert [r.stance for r in out] == ["Neutral", "Neutral"]
    assert all(r.probs["Neutral"] == 1.0 for r in out)


def test_baseline_returns_one_result_per_passage():
    assert len(AlwaysNeutralStance().label("c", ["a", "b", "c"])) == 3


def test_baseline_handles_no_passages():
    assert AlwaysNeutralStance().label("c", []) == []


@pytest.mark.gpu
def test_real_nli_model_separates_support_from_refutation():
    """The end-to-end check the mapping test cannot make: does it actually work?

    Needs weights and a GPU, so it is skipped in CI. Run locally with
    `pytest -m gpu`.
    """
    pytest.importorskip("torch")
    pytest.importorskip("transformers")

    stage = NLIStance(batch_size=2)
    claim = "The Eiffel Tower is in Paris."
    out = stage.label(claim, [
        "The Eiffel Tower, located in Paris, France, was completed in 1889.",
        "The Eiffel Tower stands in Berlin, Germany, and never left it.",
        "Cats are popular household pets.",
    ])
    assert out[0].stance == "Supports"
    assert out[1].stance == "Refutes"
    assert out[2].stance == "Neutral"


# -----------------------------------------------------------------------------
# Phase 5: the TF-IDF arms, and the pair-data path into --stage stance
# -----------------------------------------------------------------------------


def _tiny_stance_data():
    claims = {"Vaccines alter DNA.": "Refutes", "The bridge opened in 2020.": "Supports",
              "A comet will hit in May.": "Neutral"}
    x, y = [], []
    for claim, label in claims.items():
        for evidence in ("Officials responded to the report.",
                         f"Evidence about: {claim}", "A second source discussed it."):
            x.append({"claim": claim, "evidence": evidence})
            y.append(label)
    return x, y


def test_an_untrained_tfidf_arm_refuses_and_says_how_to_train_it(tmp_path):
    from stance.tfidf import StanceModelMissing, TfidfStance

    with pytest.raises(StanceModelMissing, match="train_stance_tfidf"):
        TfidfStance(model_path=tmp_path / "missing.joblib").label("c", ["e"])


@pytest.mark.parametrize("claim_only", [False, True])
def test_tfidf_arms_return_a_distribution_over_all_three_stances(tmp_path, claim_only):
    import joblib

    from stance.tfidf import TfidfClaimOnlyStance, TfidfStance, build_pipeline

    x, y = _tiny_stance_data()
    path = tmp_path / "m.joblib"
    joblib.dump(build_pipeline(claim_only).fit(x, y), path)
    cls = TfidfClaimOnlyStance if claim_only else TfidfStance
    results = cls(model_path=path).label("Vaccines alter DNA.", ["one", "two"])
    assert len(results) == 2
    for r in results:
        assert set(r.probs) == {"Supports", "Refutes", "Neutral"}
        assert sum(r.probs.values()) == pytest.approx(1.0)
        assert r.stance == max(r.probs, key=r.probs.get)


def test_the_claim_only_twin_cannot_see_the_evidence(tmp_path):
    """The control's whole value is that evidence changes nothing for it."""
    import joblib

    from stance.tfidf import TfidfClaimOnlyStance, build_pipeline

    x, y = _tiny_stance_data()
    path = tmp_path / "m.joblib"
    joblib.dump(build_pipeline(True).fit(x, y), path)
    a, b = TfidfClaimOnlyStance(model_path=path).label(
        "Vaccines alter DNA.", ["It is true.", "Completely different words entirely."])
    assert a.probs == pytest.approx(b.probs)


def test_load_pairs_refuses_a_single_text_split(tmp_path, monkeypatch):
    """--stage stance needs claim and evidence; a claim-only split cannot feed it."""
    from common.io_jsonl import write_jsonl
    from pipeline import batch

    monkeypatch.setattr(batch, "INTERIM", tmp_path)
    write_jsonl(tmp_path / "averitec" / "dev.jsonl", [{"uid": "u", "text": "a claim"}])
    with pytest.raises(ValueError, match="not a pair dataset"):
        batch.load_pairs(Path("data/splits/averitec/dev.jsonl"))
