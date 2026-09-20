"""Metric tests: hand-computed values, then scikit-learn as an independent oracle.

A metric checked only against itself is not checked. The hand-computed cases
pin the definition; the sklearn cases catch the kind of error where a plausible
implementation quietly disagrees with the rest of the field.
"""

from __future__ import annotations

import itertools
import math

import pytest
from sklearn.metrics import accuracy_score, f1_score

from eval.metrics import (
    accuracy,
    coverage_accuracy_curve,
    expected_calibration_error,
    macro_f1,
    per_class_scores,
    recall_at_k,
    reciprocal_rank,
    retrieval_metrics,
    success_at_k,
)

LABELS = ("Supported", "Refuted", "NEI", "NotAClaim")


# -----------------------------------------------------------------------------
# Retrieval, worked out by hand
# -----------------------------------------------------------------------------


def test_recall_at_k_counts_the_relevant_set_not_the_hits():
    # 2 of the 3 relevant documents are in the top 3.
    assert recall_at_k(["a", "b", "x", "c"], {"a", "b", "z"}, 3) == pytest.approx(2 / 3)


def test_success_at_k_is_binary():
    assert success_at_k(["x", "y", "a"], {"a"}, 3) == 1.0
    assert success_at_k(["x", "y", "a"], {"a"}, 2) == 0.0


def test_reciprocal_rank_uses_the_first_hit():
    assert reciprocal_rank(["x", "a", "a"], {"a"}) == pytest.approx(0.5)
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_mrr_is_the_mean_of_reciprocal_ranks():
    pairs = [(["a", "x"], {"a"}), (["x", "y", "b"], {"b"})]
    # 1/1 and 1/3 -> (1 + 0.3333) / 2
    assert retrieval_metrics(pairs, ks=(1,))["mrr"] == pytest.approx((1 + 1 / 3) / 2)


def test_queries_with_no_relevant_documents_are_skipped_not_scored_zero():
    """Scoring them 0 would silently drag every retrieval number down."""
    pairs = [(["a"], {"a"}), (["x"], set())]
    out = retrieval_metrics(pairs, ks=(1,))
    assert out["n"] == 1.0
    assert out["n_skipped_no_relevant"] == 1.0
    assert out["recall@1"] == 1.0


def test_retrieval_metrics_on_empty_input_does_not_divide_by_zero():
    assert retrieval_metrics([], ks=(1, 5))["n"] == 0.0


@pytest.mark.parametrize("fn", [recall_at_k, success_at_k])
def test_empty_relevant_set_is_an_error_not_a_silent_zero(fn):
    with pytest.raises(ValueError):
        fn(["a"], set(), 1)


# -----------------------------------------------------------------------------
# Classification, worked out by hand
# -----------------------------------------------------------------------------


def test_per_class_scores_hand_computed():
    y_true = ["Supported", "Supported", "Refuted", "NEI"]
    y_pred = ["Supported", "Refuted", "Refuted", "NEI"]
    scores = per_class_scores(y_true, y_pred, LABELS)

    # Supported: tp=1, fp=0, fn=1 -> P=1.0, R=0.5, F1=2/3
    assert scores["Supported"]["precision"] == pytest.approx(1.0)
    assert scores["Supported"]["recall"] == pytest.approx(0.5)
    assert scores["Supported"]["f1"] == pytest.approx(2 / 3)
    # Refuted: tp=1, fp=1, fn=0 -> P=0.5, R=1.0, F1=2/3
    assert scores["Refuted"]["f1"] == pytest.approx(2 / 3)
    # NotAClaim never appears at all.
    assert scores["NotAClaim"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0.0}


def test_macro_f1_averages_over_absent_classes_too():
    """The definitional choice that matters most.

    Averaging only over labels that appear would reward a model for never
    predicting a rare class -- and Punjabi has rare classes.
    """
    y_true = ["Supported", "Refuted"]
    y_pred = ["Supported", "Refuted"]
    # Perfect on the two present classes, but 4 classes were declared.
    assert macro_f1(y_true, y_pred, LABELS) == pytest.approx(0.5)
    assert macro_f1(y_true, y_pred, ("Supported", "Refuted")) == pytest.approx(1.0)


def test_confusion_and_accuracy_hand_computed():
    y_true = ["Supported", "Refuted", "NEI", "NEI"]
    y_pred = ["Supported", "NEI", "NEI", "Supported"]
    assert accuracy(y_true, y_pred) == pytest.approx(0.5)


def test_length_mismatch_is_rejected():
    with pytest.raises(ValueError, match="length mismatch"):
        macro_f1(["Supported"], ["Supported", "Refuted"], LABELS)


# -----------------------------------------------------------------------------
# scikit-learn as an independent oracle
# -----------------------------------------------------------------------------

ORACLE_CASES = [
    (["Supported", "Refuted", "NEI", "Supported", "NEI", "Refuted", "Supported"],
     ["Supported", "NEI", "NEI", "Refuted", "NEI", "Refuted", "Supported"]),
    (["Supported"] * 5 + ["Refuted"] * 3, ["Supported"] * 8),
    (["NotAClaim", "NEI", "NEI", "Refuted"], ["NEI", "NEI", "Refuted", "NotAClaim"]),
    (["Refuted"] * 6, ["Supported"] * 6),
]


@pytest.mark.parametrize("y_true,y_pred", ORACLE_CASES)
def test_macro_f1_matches_sklearn(y_true, y_pred):
    ours = macro_f1(y_true, y_pred, LABELS)
    theirs = f1_score(y_true, y_pred, labels=list(LABELS), average="macro", zero_division=0)
    assert ours == pytest.approx(theirs)


@pytest.mark.parametrize("y_true,y_pred", ORACLE_CASES)
def test_accuracy_matches_sklearn(y_true, y_pred):
    assert accuracy(y_true, y_pred) == pytest.approx(accuracy_score(y_true, y_pred))


@pytest.mark.parametrize("y_true,y_pred", ORACLE_CASES)
def test_per_class_f1_matches_sklearn(y_true, y_pred):
    ours = per_class_scores(y_true, y_pred, LABELS)
    theirs = f1_score(y_true, y_pred, labels=list(LABELS), average=None, zero_division=0)
    for label, expected in zip(LABELS, theirs):
        assert ours[label]["f1"] == pytest.approx(expected)


# -----------------------------------------------------------------------------
# Calibration and abstention
# -----------------------------------------------------------------------------


def test_perfect_calibration_scores_zero_ece():
    # Confidence 1.0 and always right; confidence 0.0 and always wrong.
    conf = [1.0, 1.0, 0.0, 0.0]
    correct = [True, True, False, False]
    assert expected_calibration_error(conf, correct, n_bins=10) == pytest.approx(0.0)


def test_maximally_overconfident_scores_ece_one():
    assert expected_calibration_error([1.0, 1.0], [False, False]) == pytest.approx(1.0)


def test_ece_rejects_confidence_outside_unit_interval():
    with pytest.raises(ValueError, match="outside"):
        expected_calibration_error([1.5], [True])


def test_coverage_accuracy_curve_improves_as_coverage_drops():
    """The Phase 6 headline: declining the uncertain tail should raise accuracy."""
    conf = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
    correct = [True, True, True, True, False, False]
    curve = coverage_accuracy_curve(conf, correct, n_points=6)
    assert curve[-1]["coverage"] == pytest.approx(1.0)
    assert curve[-1]["accuracy"] == pytest.approx(4 / 6)
    # At the highest-confidence end accuracy is perfect.
    assert curve[0]["accuracy"] == pytest.approx(1.0)
    # Monotone non-increasing in this construction.
    accs = [point["accuracy"] for point in curve]
    assert all(earlier >= later or math.isclose(earlier, later)
               for earlier, later in itertools.pairwise(accs))


def test_coverage_curve_on_empty_input():
    assert coverage_accuracy_curve([], []) == []
