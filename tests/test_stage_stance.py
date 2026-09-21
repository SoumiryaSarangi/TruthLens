"""Stance stage tests.

The mapping from NLI labels to stance is the whole of the modelling here, and
getting it backwards would invert every verdict while everything still ran and
produced plausible numbers. So it is asserted directly, and the real model is
exercised separately behind the `gpu` marker.
"""

from __future__ import annotations

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
