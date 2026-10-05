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
    area_under_coverage_curve,
    coverage_accuracy_curve,
    expected_calibration_error,
    fast_path_metrics,
    macro_f1,
    per_class_scores,
    recall_at_k,
    reciprocal_rank,
    retrieval_metrics,
    success_at_k,
)

LABELS = ("Supported", "Refuted", "Conflicting", "NEI", "NotAClaim")


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
    # Perfect on the two present classes, but 5 classes were declared.
    assert macro_f1(y_true, y_pred, LABELS) == pytest.approx(2 / 5)
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


# -----------------------------------------------------------------------------
# The fast path (FR-8)
# -----------------------------------------------------------------------------


def test_area_under_a_flat_curve_is_the_flat_value():
    """The property the `always_match` baseline rests on.

    A score carrying no information traces a flat coverage-accuracy curve at
    Success@1, so AUCC must come back as exactly Success@1 -- otherwise the
    delta against that baseline is not "signal in the score" but an artefact of
    how the area was normalised.
    """
    flat = [{"coverage": 0.25, "accuracy": 0.5},
            {"coverage": 0.50, "accuracy": 0.5},
            {"coverage": 1.00, "accuracy": 0.5}]
    assert area_under_coverage_curve(flat) == pytest.approx(0.5)


def test_area_under_coverage_curve_hand_computed():
    """Reuses the curve above: conf 0.9..0.4, correct [T,T,T,T,F,F], n_points=6.

    Coverages are i/6 and accuracies 1, 1, 1, 1, 4/5, 2/3. Trapezoid at h=1/6 is
    (1/6)(1 + 1 + 1 + 9/10 + 11/15) = 139/180. The coverage span is 1 - 1/6 = 5/6,
    so AUCC = (139/180)(6/5) = 139/150.
    """
    curve = coverage_accuracy_curve([0.9, 0.8, 0.7, 0.6, 0.5, 0.4],
                                    [True] * 4 + [False] * 2, n_points=6)
    assert area_under_coverage_curve(curve) == pytest.approx(139 / 150)


def test_fast_path_metrics_at_one_tau_hand_computed():
    """Nine queries, scores 0.9 down to 0.1, correct = [T,T,T,F,T,F,F,F,F].

    At tau=0.55 four are accepted (0.9, 0.8, 0.7, 0.6) and three of those are
    right: coverage 4/9, precision 3/4, yield 3/9.
    """
    scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    correct = [True, True, True, False, True, False, False, False, False]
    wrong = [0.85, 0.75, 0.65, 0.6, 0.45, 0.4, 0.3, 0.2, 0.1]
    m = fast_path_metrics(scores, correct, wrong, tau=0.55, taus=[0.55])
    assert m["fastpath_coverage"] == pytest.approx(4 / 9)
    assert m["fastpath_precision"] == pytest.approx(3 / 4)
    assert m["fastpath_yield"] == pytest.approx(1 / 3)
    assert m["false_accept_rate"] == pytest.approx(4 / 9)
    assert m["n"] == 9.0
    assert m["n_accepted"] == 4.0


def test_precision_is_zero_not_nan_when_nothing_is_accepted():
    """Vacuous, and documented as such -- read `n_accepted` beside it."""
    m = fast_path_metrics([0.1], [False], [0.1], tau=0.9)
    assert m["fastpath_precision"] == 0.0
    assert m["n_accepted"] == 0.0
    assert m["fastpath_coverage"] == 0.0


def test_a_natural_negative_scores_on_the_negative_arm_only():
    """`relevant_ids: []` means no correct answer exists for that query.

    Counting it as a wrong positive would drag precision down for a reason that
    is not the gate's fault -- the gate cannot pick a right answer that is not
    in the corpus.
    """
    m = fast_path_metrics([0.9, 0.9], [True, None], [0.5, 0.9], tau=0.8)
    assert m["n"] == 1.0
    assert m["fastpath_precision"] == 1.0
    assert m["n_natural_negatives"] == 1.0
    assert m["false_accept_rate"] == pytest.approx(1 / 2)


def test_a_query_whose_every_candidate_is_gold_is_skipped_not_scored():
    m = fast_path_metrics([0.9], [True], [None], tau=0.5)
    assert m["n_skipped_no_wrong_candidate"] == 1.0
    assert m["n_negatives"] == 0.0
    assert m["false_accept_rate"] == 0.0


def test_the_curve_carries_every_requested_tau_plus_the_operating_point():
    """The chosen tau must be visible on the table it was chosen from."""
    m = fast_path_metrics([0.9, 0.5], [True, False], [0.4, 0.5],
                          tau=0.7, taus=[0.6, 0.8])
    assert [point["tau"] for point in m["curve"]] == [0.6, 0.7, 0.8]


def test_a_gate_that_never_declines_reports_success_at_one():
    """tau below every score measures Success@1 under another name.

    Pinned because it is the failure mode of putting a cosine-calibrated tau in
    front of a retriever whose scores are on a different scale.
    """
    m = fast_path_metrics([0.9, 0.8, 0.7], [True, False, True], [0.1, 0.1, 0.1],
                          tau=0.0)
    assert m["fastpath_coverage"] == 1.0
    assert m["fastpath_precision"] == pytest.approx(2 / 3)


def test_mismatched_array_lengths_are_refused():
    with pytest.raises(ValueError, match="same length"):
        fast_path_metrics([0.9, 0.8], [True], [0.1], tau=0.5)


# -----------------------------------------------------------------------------
# Claim spans and normalization (FR-7)
# -----------------------------------------------------------------------------

from eval.metrics import chrf, normalization_metrics, span_metrics  # noqa: E402

BEGIN, INSIDE, OUTSIDE = "B-CLAIM", "I-CLAIM", "O"


def test_span_metrics_against_a_hand_worked_example():
    """Gold claim tokens at 1,2,3; predicted at 2,3,4.

    tp = 2 (positions 2 and 3), fp = 1 (position 4), fn = 1 (position 1).
    So precision = recall = 2/3 and F1 = 2/3.
    """
    m = span_metrics([[OUTSIDE, OUTSIDE, BEGIN, INSIDE, INSIDE]], [[OUTSIDE, BEGIN, INSIDE, INSIDE, OUTSIDE]])
    assert m["token_precision"] == pytest.approx(2 / 3)
    assert m["token_recall"] == pytest.approx(2 / 3)
    assert m["token_f1"] == pytest.approx(2 / 3)
    assert m["exact_span_match"] == 0.0


def test_span_metrics_perfect_and_disjoint():
    assert span_metrics([[BEGIN, INSIDE, OUTSIDE]], [[BEGIN, INSIDE, OUTSIDE]])["token_f1"] == 1.0
    assert span_metrics([[OUTSIDE, OUTSIDE, BEGIN]], [[BEGIN, INSIDE, OUTSIDE]])["token_f1"] == 0.0


def test_an_all_outside_prediction_scores_zero_not_two_thirds():
    """`O` is not scored as a class, and this is why.

    About half of every X-CLAIM post is not the claim, so a three-class average
    would reward a model that predicted `O` everywhere and found nothing.
    """
    assert span_metrics([[OUTSIDE, OUTSIDE, OUTSIDE]], [[BEGIN, INSIDE, OUTSIDE]])["token_f1"] == 0.0


def test_whole_post_prediction_gives_recall_one():
    """The shape of the `whole_post_span` baseline, on a 50%-claim corpus."""
    m = span_metrics([[BEGIN, INSIDE, INSIDE, INSIDE]], [[BEGIN, INSIDE, OUTSIDE, OUTSIDE]])
    assert m["token_recall"] == 1.0
    assert m["token_precision"] == pytest.approx(0.5)
    assert m["token_f1"] == pytest.approx(2 / 3)


def test_span_metrics_refuses_a_length_mismatch():
    """A misaligned prediction makes every position meaningless."""
    with pytest.raises(ValueError, match="tags but gold has"):
        span_metrics([[BEGIN, INSIDE]], [[BEGIN, INSIDE, OUTSIDE]])


def test_chrf_identical_and_disjoint():
    assert chrf("the government said", "the government said") == pytest.approx(1.0)
    assert chrf("aaaa", "bbbb") == 0.0


def test_chrf_against_a_hand_worked_example():
    """`abc` vs `abd`, beta=2.

    1-grams {a,b,c} vs {a,b,d}: overlap 2, so p = r = 2/3.
    2-grams {ab,bc} vs {ab,bd}: overlap 1, so p = r = 1/2.
    3-grams {abc} vs {abd}:     overlap 0, so p = r = 0.
    Orders 4-6 have no n-grams on either side and are skipped, not scored zero:
    a short reference must not be punished for being short.
    Mean p = mean r = (2/3 + 1/2 + 0)/3 = 7/18, and chrF collapses to that when
    precision equals recall.
    """
    assert chrf("abc", "abd") == pytest.approx(7 / 18)


def test_normalization_metrics_reports_chrf_and_exact_match():
    m = normalization_metrics(["a b", "x"], ["a b", "y"])
    assert m["exact_match"] == pytest.approx(0.5)
    assert m["chrf"] == pytest.approx(0.5)
    assert m["n"] == 2.0


# -----------------------------------------------------------------------------
# Calibration and abstention (Phase 6)
# -----------------------------------------------------------------------------


def test_reliability_bins_by_hand():
    from eval.metrics import reliability_bins
    bins = reliability_bins([0.15, 0.18, 0.95], [True, False, True], n_bins=10)
    assert [(b["lo"], b["n"], b["accuracy"]) for b in bins] == [(0.1, 2.0, 0.5),
                                                               (0.9, 1.0, 1.0)]


def test_operating_point_is_the_lowest_tau_within_the_coverage_target():
    from eval.metrics import operating_point
    y = ["A", "A", "B", "B", "A"]
    p = ["A", "B", "B", "A", "A"]
    conf = [0.9, 0.8, 0.8, 0.4, 0.3]
    op = operating_point(y, p, conf, ["A", "B"], coverage_target=0.6)
    # tau=0.8 keeps 3/5 = 0.6 (the tie at 0.8 is kept together); tau=0.4 keeps 0.8.
    assert op["tau"] == 0.8 and op["coverage"] == 0.6
    assert op["selective_accuracy"] == pytest.approx(2 / 3)


def test_operating_point_when_ties_make_the_target_unreachable():
    from eval.metrics import operating_point
    op = operating_point(["A"] * 4, ["A"] * 4, [0.5] * 4, ["A"], coverage_target=0.6)
    assert op["coverage"] == 0.0 and op["n_kept"] == 0.0 and op["tau"] > 0.5


def test_selective_at_a_fixed_tau_applies_it_without_choosing():
    from eval.metrics import selective_at_tau
    y = ["A", "A", "B", "B", "A"]
    p = ["A", "B", "B", "A", "A"]
    conf = [0.9, 0.8, 0.8, 0.4, 0.3]
    # tau=0.4 keeps rows 0-3 (>= is inclusive), 2 of them right.
    at = selective_at_tau(y, p, conf, ["A", "B"], tau=0.4)
    assert at["tau"] == 0.4 and at["coverage"] == 0.8 and at["n_kept"] == 4.0
    assert at["selective_accuracy"] == pytest.approx(0.5)
    none = selective_at_tau(y, p, conf, ["A", "B"], tau=0.95)
    assert none["coverage"] == 0.0 and none["selective_macro_f1"] == 0.0


def test_calibration_metrics_reports_at_tau_only_when_asked():
    from eval.metrics import calibration_metrics
    args = (["A", "B"], ["A", "A"], [0.9, 0.6], ["A", "B"])
    assert "at_tau" not in calibration_metrics(*args)
    assert calibration_metrics(*args, tau=0.7)["at_tau"]["coverage"] == 0.5


def test_calibration_metrics_curve_carries_macro_f1():
    from eval.metrics import calibration_metrics
    out = calibration_metrics(["A", "B"], ["A", "A"], [0.9, 0.6], ["A", "B"], n_points=2)
    assert out["coverage_curve"][0]["macro_f1"] == pytest.approx(0.5)   # A right, B absent
    assert out["ece"] == pytest.approx((abs(1 - 0.9) + abs(0 - 0.6)) / 2)



def test_paired_bootstrap_of_a_system_against_itself_is_exactly_zero():
    from eval.metrics import paired_bootstrap_delta
    y = ["A", "B", "A", "B"] * 10
    p = ["A", "A", "B", "B"] * 10
    out = paired_bootstrap_delta(y, p, p, ["A", "B"], n_resamples=200)
    assert out["delta"] == out["ci95_low"] == out["ci95_high"] == 0.0
    assert out["p_a_better"] == 0.0


def test_paired_bootstrap_of_a_clearly_better_system_excludes_zero():
    from eval.metrics import paired_bootstrap_delta
    y = ["A", "B"] * 50
    out = paired_bootstrap_delta(y, y, ["A"] * 100, ["A", "B"], n_resamples=200)
    assert out["delta"] > 0 and out["ci95_low"] > 0 and out["p_a_better"] == 1.0


import eval.metrics as M  # noqa: E402

# -- false-label rate (live verdict on FEVER) ----------------------------------


def test_wilson_interval_matches_a_hand_computed_value():
    lo, hi = M.wilson_interval(4, 200)          # 2%: Wilson (0.0078, 0.0503)
    assert lo == pytest.approx(0.0078, abs=5e-4) and hi == pytest.approx(0.0503, abs=5e-4)
    assert M.wilson_interval(3, 200)[1] < 0.05 < M.wilson_interval(4, 200)[1]   # the protocol's cut
    assert M.wilson_interval(0, 0) == (0.0, 0.0)
    assert M.wilson_interval(0, 50)[0] == pytest.approx(0.0) and M.wilson_interval(50, 50)[1] == pytest.approx(1.0)


def test_false_label_rate_counts_only_rows_whose_gold_is_something_else():
    y_true = ["Supported", "Supported", "Refuted", "Refuted", "NEI", "NEI"]
    y_pred = ["Supported", "Refuted", "Supported", "Refuted", "Supported", "NEI"]
    out = M.false_label_rate(y_true, y_pred, "Supported")
    assert out["k"] == 2 and out["n"] == 4 and out["rate"] == 0.5     # the true claim doesn't count
    assert out["wilson_lo"] < 0.5 < out["wilson_hi"]


def test_classification_metrics_reports_it_only_when_asked():
    base = M.classification_metrics(["A", "B"], ["A", "B"], ["A", "B"])
    asked = M.classification_metrics(["A", "B"], ["A", "A"], ["A", "B"], false_label="A")
    assert "false_label_rate" not in base and asked["false_label_rate"]["k"] == 1.0


def test_real_claims_metrics_counts_and_applies_the_transfer_rule():
    from eval.metrics import real_claims_metrics

    good = [{"gold": "T", "shown": "Supported", "decider": "wikipedia"}] * 60 + [{"gold": "F", "shown": "Refuted", "decider": "wikipedia"}] * 30
    good += [{"gold": "F", "shown": None, "decider": None}] * 120 + [{"gold": "U", "shown": "Refuted", "decider": "factcheck"}] * 2
    m = real_claims_metrics(good)
    assert m["all"]["shown"] == 92 and m["all"]["decidable_shown"] == 90 and m["all"]["precision"] == 1.0
    assert m["all"]["shown_on_unverifiable"] == 2 and m["all"]["false_supported"] == 0
    assert m["transfers"] == "transfers" and m["by_decider"]["factcheck"]["shown"] == 2


def test_real_claims_metrics_flags_false_supported_and_low_precision():
    from eval.metrics import real_claims_metrics

    bad = [{"gold": "F", "shown": "Supported", "decider": "wikipedia"}] * 20 + [{"gold": "T", "shown": "Supported", "decider": "wikipedia"}] * 20
    bad += [{"gold": "F", "shown": None, "decider": None}] * 100
    m = real_claims_metrics(bad)
    assert m["all"]["false_supported"] == 20 and m["all"]["precision"] == 0.5 and m["transfers"] == "does not transfer"
    only_fs = [{"gold": "T", "shown": "Supported", "decider": "wikipedia"}] * 80 + [{"gold": "F", "shown": "Supported", "decider": "wikipedia"}] * 2 + [{"gold": "F", "shown": None, "decider": None}] * 38
    assert real_claims_metrics(only_fs)["transfers"] == "partly transfers"


def test_paired_flip_counts():
    from eval.metrics import paired_flip_counts

    plain = {"1": ("T", "Supported"), "2": ("F", None), "3": ("F", "Refuted"), "4": ("F", "Refuted"), "5": ("U", None)}
    chatty = {"1": ("T", "Supported"), "2": ("F", "Refuted"), "3": ("F", None), "4": ("F", "Supported"), "5": ("U", None)}
    m = paired_flip_counts(plain, chatty)
    assert m == {"n": 5, "both_silent": 1, "silent_to_shown": 1, "shown_to_silent": 1, "same_verdict": 1, "flipped": 1,
                 "plain_correct": 3, "chatty_correct": 2}

