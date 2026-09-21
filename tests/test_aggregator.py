"""Every row of the SYSTEM_DESIGN.md §6 aggregation table.

The aggregator is the whole of Phase 1's "modelling" for the verdict, and it is
a fixed rule, so there is no excuse for any row of it being untested.
"""

from __future__ import annotations

import pytest

from pipeline.aggregate import RuleAggregator


def probs(sup: float, ref: float, neu: float | None = None) -> dict[str, float]:
    return {"Supports": sup, "Refutes": ref,
            "Neutral": 1.0 - sup - ref if neu is None else neu}


@pytest.fixture
def agg():
    return RuleAggregator(threshold=0.5)


def test_strong_support_is_supported(agg):
    assert agg.aggregate([probs(0.9, 0.05)]).verdict == "Supported"


def test_strong_refutation_is_refuted(agg):
    assert agg.aggregate([probs(0.05, 0.9)]).verdict == "Refuted"


def test_strong_both_is_conflicting(agg):
    """The corner the rule exists for: evidence that disagrees with itself.

    Note it is max over PASSAGES, so one supporting and one refuting passage
    yields Conflicting even though neither passage is itself conflicted.
    """
    out = agg.aggregate([probs(0.9, 0.05), probs(0.05, 0.8)])
    assert out.verdict == "Conflicting"
    assert out.max_supports == pytest.approx(0.9)
    assert out.max_refutes == pytest.approx(0.8)


def test_neither_side_confident_is_nei(agg):
    assert agg.aggregate([probs(0.3, 0.2, 0.5)]).verdict == "NEI"


def test_no_passages_is_nei_with_zero_confidence(agg):
    """FR-12: no evidence is not a verdict."""
    out = agg.aggregate([])
    assert out.verdict == "NEI"
    assert out.confidence == 0.0


@pytest.mark.parametrize("sup,ref,expected", [
    (0.50, 0.10, "Supported"),      # exactly at the threshold counts
    (0.49, 0.10, "NEI"),            # just under does not
    (0.10, 0.50, "Refuted"),
    (0.50, 0.50, "Conflicting"),
])
def test_threshold_boundaries(agg, sup, ref, expected):
    assert agg.aggregate([probs(sup, ref, 1.0 - sup - ref)]).verdict == expected


def test_confidence_is_the_winning_probability(agg):
    assert agg.aggregate([probs(0.77, 0.1)]).confidence == pytest.approx(0.77)


def test_nei_confidence_grows_as_evidence_weakens(agg):
    """NEI confidence is how firmly the evidence declined to commit.

    An abstention threshold is later applied to this number, so it has to move
    in the sensible direction.
    """
    weak = agg.aggregate([probs(0.1, 0.1, 0.8)]).confidence
    borderline = agg.aggregate([probs(0.45, 0.1, 0.45)]).confidence
    assert weak > borderline


def test_threshold_is_configurable(agg):
    strict = RuleAggregator(threshold=0.95)
    assert strict.aggregate([probs(0.9, 0.05)]).verdict == "NEI"
    assert agg.aggregate([probs(0.9, 0.05)]).verdict == "Supported"
