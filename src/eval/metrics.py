"""Metric definitions. Pure functions, no I/O, no globals.

Every number in the report comes from here, so each function is small enough to
check by hand and is unit-tested twice: against values worked out on paper, and
against scikit-learn as an independent oracle.

Definitional choices that are easy to get silently wrong, fixed here once:

* macro-F1 averages over EVERY label in the declared label set, including
  labels with zero support, which contribute F1 = 0. Averaging only over the
  labels that happen to appear would make a model look better simply for never
  predicting a rare class, and Punjabi has classes that will be rare.
* A class with no predictions and no gold instances scores 0, not NaN, so the
  macro average stays defined.
* A retrieval query with no relevant documents is skipped rather than scored 0;
  such a query measures nothing. The number skipped is reported alongside.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Sequence
from typing import Any

# -----------------------------------------------------------------------------
# Retrieval
# -----------------------------------------------------------------------------


def recall_at_k(ranked: Sequence[str], relevant: Collection[str], k: int) -> float:
    """Fraction of the relevant set appearing in the top k."""
    if not relevant:
        raise ValueError("recall_at_k requires at least one relevant id")
    rel = set(relevant)
    hits = sum(1 for doc in ranked[:k] if doc in rel)
    return hits / len(rel)


def success_at_k(ranked: Sequence[str], relevant: Collection[str], k: int) -> float:
    """1.0 if any relevant document is in the top k, else 0.0."""
    if not relevant:
        raise ValueError("success_at_k requires at least one relevant id")
    rel = set(relevant)
    return 1.0 if any(doc in rel for doc in ranked[:k]) else 0.0


def reciprocal_rank(ranked: Sequence[str], relevant: Collection[str]) -> float:
    """1 / rank of the first relevant document; 0.0 if none is retrieved."""
    if not relevant:
        raise ValueError("reciprocal_rank requires at least one relevant id")
    rel = set(relevant)
    for i, doc in enumerate(ranked, start=1):
        if doc in rel:
            return 1.0 / i
    return 0.0


def retrieval_metrics(
    pairs: Sequence[tuple[Sequence[str], Collection[str]]],
    ks: Sequence[int] = (1, 5, 10),
) -> dict[str, float]:
    """Aggregate Recall@k, Success@k and MRR over (ranked, relevant) pairs."""
    scored = [(r, rel) for r, rel in pairs if rel]
    n_skipped = len(pairs) - len(scored)
    if not scored:
        return {"n": 0.0, "n_skipped_no_relevant": float(n_skipped)}

    out: dict[str, float] = {"n": float(len(scored))}
    if n_skipped:
        out["n_skipped_no_relevant"] = float(n_skipped)
    for k in ks:
        out[f"recall@{k}"] = sum(recall_at_k(r, rel, k) for r, rel in scored) / len(scored)
        out[f"success@{k}"] = sum(success_at_k(r, rel, k) for r, rel in scored) / len(scored)
    out["mrr"] = sum(reciprocal_rank(r, rel) for r, rel in scored) / len(scored)
    return out


# -----------------------------------------------------------------------------
# Classification
# -----------------------------------------------------------------------------


def confusion_matrix(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str],
) -> dict[str, dict[str, int]]:
    """matrix[gold][predicted] = count."""
    if len(y_true) != len(y_pred):
        raise ValueError(f"length mismatch: {len(y_true)} gold vs {len(y_pred)} predicted")
    matrix = {g: dict.fromkeys(labels, 0) for g in labels}
    for gold, pred in zip(y_true, y_pred):
        matrix[gold][pred] += 1
    return matrix


def per_class_scores(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str],
) -> dict[str, dict[str, float]]:
    """Precision, recall, F1 and support for each label in the declared set."""
    if len(y_true) != len(y_pred):
        raise ValueError(f"length mismatch: {len(y_true)} gold vs {len(y_pred)} predicted")
    out: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for g, p in zip(y_true, y_pred) if g == label and p == label)
        fp = sum(1 for g, p in zip(y_true, y_pred) if g != label and p == label)
        fn = sum(1 for g, p in zip(y_true, y_pred) if g == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[label] = {
            "precision": precision, "recall": recall, "f1": f1, "support": float(tp + fn),
        }
    return out


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]) -> float:
    """Unweighted mean F1 over every label in `labels`, zero-support included."""
    if not labels:
        raise ValueError("macro_f1 requires a non-empty label set")
    scores = per_class_scores(y_true, y_pred, labels)
    return sum(s["f1"] for s in scores.values()) / len(labels)


def accuracy(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    if not y_true:
        return 0.0
    return sum(1 for g, p in zip(y_true, y_pred) if g == p) / len(y_true)


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials ((0, 0) when n is 0)."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def false_label_rate(y_true: Sequence[str], y_pred: Sequence[str], label: str) -> dict[str, float]:
    """Of the rows whose gold is NOT `label`, the share predicted `label`, with its
    95% Wilson interval. For `Supported` this is the false-Supported rate: a false
    or unverifiable claim called true, the worst error a misinformation tool makes."""
    others = [(t, p) for t, p in zip(y_true, y_pred, strict=True) if t != label]
    k = sum(1 for _, p in others if p == label)
    lo, hi = wilson_interval(k, len(others))
    return {"k": float(k), "n": float(len(others)),
            "rate": k / len(others) if others else 0.0, "wilson_lo": lo, "wilson_hi": hi}


def classification_metrics(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str],
    false_label: str | None = None,
) -> dict[str, Any]:
    out = {
        "n": float(len(y_true)),
        "accuracy": accuracy(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred, labels),
        "per_class": per_class_scores(y_true, y_pred, labels),
        "confusion": confusion_matrix(y_true, y_pred, labels),
    }
    if false_label is not None:
        out["false_label_rate"] = false_label_rate(y_true, y_pred, false_label)
    return out


# -----------------------------------------------------------------------------
# Calibration and abstention (written now; the headline result of Phase 6)
# -----------------------------------------------------------------------------


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10,
) -> float:
    """Equal-width-bin ECE: mean |accuracy - confidence| weighted by bin size."""
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    if not confidences:
        return 0.0
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for conf, ok in zip(confidences, correct):
        if not 0.0 <= conf <= 1.0:
            raise ValueError(f"confidence {conf} outside [0, 1]")
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, ok))
    total = len(confidences)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - avg_conf)
    return ece


def reliability_bins(
    confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10,
) -> list[dict[str, float]]:
    """The reliability diagram ECE summarises: one row per non-empty bin."""
    rows: list[dict[str, float]] = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, c in enumerate(confidences)
               if min(int(c * n_bins), n_bins - 1) == b]
        if not idx:
            continue
        rows.append({
            "lo": lo, "hi": hi, "n": float(len(idx)),
            "mean_confidence": sum(confidences[i] for i in idx) / len(idx),
            "accuracy": sum(1 for i in idx if correct[i]) / len(idx),
        })
    return rows


def operating_point(
    y_true: Sequence[str], y_pred: Sequence[str], confidences: Sequence[float],
    labels: Sequence[str], coverage_target: float,
) -> dict[str, float]:
    """The LOWEST threshold tau whose coverage is still <= `coverage_target`.

    Threshold semantics, not rank semantics: a claim is answered iff its
    confidence >= tau, which is exactly what the served pipeline does with
    `tau_abstain` (abstain when confidence < tau). Ties are therefore kept or
    dropped together, so the coverage achieved can sit below the target.
    The criterion is fixed in the Phase 6 plan before any number was seen.
    """
    n = len(confidences)
    if not n:
        return {"tau": 1.0, "coverage": 0.0, "n_kept": 0.0}
    best = None
    for tau in sorted(set(confidences)):
        kept = [i for i in range(n) if confidences[i] >= tau]
        if len(kept) / n <= coverage_target:
            best = (tau, kept)
            break
    if best is None:                       # every threshold answers too much
        tau = math.nextafter(max(confidences), math.inf)
        best = (tau, [])
    tau, kept = best
    yt = [y_true[i] for i in kept]
    yp = [y_pred[i] for i in kept]
    return {
        "tau": float(tau),
        "coverage_target": float(coverage_target),
        "coverage": len(kept) / n,
        "n_kept": float(len(kept)),
        "selective_accuracy": accuracy(yt, yp),
        "selective_macro_f1": macro_f1(yt, yp, labels) if kept else 0.0,
    }


def selective_at_tau(
    y_true: Sequence[str], y_pred: Sequence[str], confidences: Sequence[float],
    labels: Sequence[str], tau: float,
) -> dict[str, float]:
    """Coverage and selective scores at a FIXED threshold chosen elsewhere.

    `operating_point` chooses tau on the rows it is given; on a test split that
    is choosing on test (FR-14 forbids it). This only applies a tau that dev
    already chose, with the same semantics: answered iff confidence >= tau.
    """
    n = len(confidences)
    kept = [i for i in range(n) if confidences[i] >= tau]
    yt = [y_true[i] for i in kept]
    yp = [y_pred[i] for i in kept]
    return {
        "tau": float(tau),
        "coverage": len(kept) / n if n else 0.0,
        "n_kept": float(len(kept)),
        "selective_accuracy": accuracy(yt, yp),
        "selective_macro_f1": macro_f1(yt, yp, labels) if kept else 0.0,
    }


def calibration_metrics(
    y_true: Sequence[str], y_pred: Sequence[str], confidences: Sequence[float],
    labels: Sequence[str], n_bins: int = 10, coverage_target: float = 0.6,
    n_points: int = 21, tau: float | None = None,
) -> dict[str, Any]:
    """ECE, its reliability bins, the coverage curve and the abstention point.

    FR-13 and FR-14. `confidence` is the probability the system attaches to the
    verdict it gave -- the number `tau_abstain` is compared against -- so that
    is what is calibrated, not the maximum of some distribution it may not have
    acted on.
    """
    correct = [g == p for g, p in zip(y_true, y_pred, strict=True)]
    curve = coverage_accuracy_curve(confidences, correct, n_points=n_points)
    order = sorted(range(len(confidences)), key=lambda i: confidences[i], reverse=True)
    for point in curve:
        kept = order[:int(point["n_kept"])]
        point["macro_f1"] = macro_f1([y_true[i] for i in kept],
                                     [y_pred[i] for i in kept], labels)
    out = {
        "ece": expected_calibration_error(confidences, correct, n_bins=n_bins),
        "mean_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
        "reliability": reliability_bins(confidences, correct, n_bins=n_bins),
        "coverage_curve": curve,
        "operating_point": operating_point(y_true, y_pred, confidences, labels,
                                           coverage_target),
    }
    if tau is not None:
        out["at_tau"] = selective_at_tau(y_true, y_pred, confidences, labels, tau)
    return out


def paired_bootstrap_delta(
    y_true: Sequence[str], pred_a: Sequence[str], pred_b: Sequence[str],
    labels: Sequence[str], n_resamples: int = 1000, seed: int = 42,
) -> dict[str, float]:
    """Macro-F1(a) - macro-F1(b), with a 95% CI from a PAIRED bootstrap.

    Paired: each resample draws the same claims for both systems, so the
    interval reflects how the two disagree on claims, not how hard the sample
    happened to be. With 35-38 claims in the rare classes, one claim moves a
    class F1 by ~0.03, and a delta inside its interval is not a finding.
    """
    import random

    n = len(y_true)
    if not n:
        return {"delta": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "p_a_better": 0.0}
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        yt = [y_true[i] for i in idx]
        deltas.append(macro_f1(yt, [pred_a[i] for i in idx], labels)
                      - macro_f1(yt, [pred_b[i] for i in idx], labels))
    deltas.sort()
    return {
        "delta": macro_f1(y_true, pred_a, labels) - macro_f1(y_true, pred_b, labels),
        "ci95_low": deltas[int(0.025 * n_resamples)],
        "ci95_high": deltas[min(int(0.975 * n_resamples), n_resamples - 1)],
        "p_a_better": sum(d > 0 for d in deltas) / n_resamples,
        "n_resamples": float(n_resamples),
    }


def coverage_accuracy_curve(
    confidences: Sequence[float], correct: Sequence[bool], n_points: int = 21,
) -> list[dict[str, float]]:
    """Accuracy as a function of coverage, for the abstention sweep.

    docs/build-plan.md calls this the headline result: accuracy at 100%
    coverage looks mediocre, accuracy at 60% coverage with the rest declined
    looks excellent, and the second is the honest deployable framing.
    """
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    if not confidences:
        return []
    order = sorted(zip(confidences, correct), key=lambda t: t[0], reverse=True)
    n = len(order)
    curve: list[dict[str, float]] = []
    for i in range(1, n_points + 1):
        coverage = i / n_points
        take = max(1, math.ceil(coverage * n))
        kept = order[:take]
        curve.append({
            "coverage": take / n,
            "n_kept": float(take),
            "accuracy": sum(1 for _, ok in kept if ok) / take,
            "threshold": kept[-1][0],
        })
    return curve


# -----------------------------------------------------------------------------
# The fast path (FR-8)
# -----------------------------------------------------------------------------
# `retrieval_metrics` above asks "does the retriever find the right fact-check".
# These ask a strictly different question over the same predictions: **does the
# SCORE say when to trust it.** Every rank metric is scale-free and every
# MultiClaim query is guaranteed to have an answer, so nothing above can tell
# you whether to resolve a post on the fast path or send it to retrieval.
#
# Two things to know before reading any number these produce:
#
# * **The negatives are made by withholding the answer.** For each query the
#   best-scoring returned candidate that is NOT gold is, by construction, wrong.
#   For a cosine scorer this is exact rather than a simulation -- a pair's score
#   does not depend on what else is in the index, so dropping the gold from the
#   returned list and dropping it from the index give the same best-remaining
#   candidate. It is only APPROXIMATE for BM25, whose IDF depends on corpus
#   composition.
# * **`false_accept_rate` is an UPPER bound.** MultiClaim's annotation is
#   incomplete: a fact-check that is not in a post's gold set may still be a
#   perfectly good match for it, and this counts every such acceptance as a
#   false one.


def area_under_coverage_curve(curve: Sequence[dict[str, float]]) -> float:
    """Trapezoid over a coverage-accuracy curve, normalised by its coverage span.

    Normalised so that a FLAT curve at p returns exactly p. That property is what
    the whole comparison rests on: a score carrying no information traces a flat
    curve at Success@1, so the `always_match` baseline scores exactly Success@1
    and the delta against it is the amount of gate-worthy signal in the score --
    not the quality of the ranking, which `task: retrieval` already measures.
    """
    points = [(float(p["coverage"]), float(p["accuracy"])) for p in curve]
    if not points:
        return 0.0
    if len(points) == 1:
        return points[0][1]
    points.sort()
    span = points[-1][0] - points[0][0]
    if span <= 0:
        return sum(a for _, a in points) / len(points)
    area = sum(
        (points[i + 1][0] - points[i][0]) * (points[i][1] + points[i + 1][1]) / 2
        for i in range(len(points) - 1)
    )
    return area / span


def fast_path_curve(
    top_scores: Sequence[float],
    top_correct: Sequence[bool | None],
    best_wrong_scores: Sequence[float | None],
    taus: Sequence[float],
) -> list[dict[str, float]]:
    """One row per tau. This table is the result; the headline is a summary of it."""
    positives = [(s, c) for s, c in zip(top_scores, top_correct, strict=True)
                 if c is not None]
    negatives = [s for s in best_wrong_scores if s is not None]
    out: list[dict[str, float]] = []
    for tau in sorted({float(t) for t in taus}):
        accepted = [c for s, c in positives if s >= tau]
        right = sum(1 for c in accepted if c)
        out.append({
            "tau": tau,
            "coverage": len(accepted) / len(positives) if positives else 0.0,
            "precision": right / len(accepted) if accepted else 0.0,
            "yield": right / len(positives) if positives else 0.0,
            "false_accept_rate": (sum(1 for s in negatives if s >= tau) / len(negatives)
                                  if negatives else 0.0),
            "n_accepted": float(len(accepted)),
        })
    return out


def fast_path_metrics(
    top_scores: Sequence[float],
    top_correct: Sequence[bool | None],
    best_wrong_scores: Sequence[float | None],
    *,
    tau: float,
    taus: Sequence[float] = (),
    n_points: int = 21,
) -> dict[str, Any]:
    """Coverage, precision and false accepts for a score-gated fast path.

    Three parallel arrays, one entry per query:

      top_scores         the top-1 score, whatever scale the retriever uses
      top_correct        True / False, or **None** when no correct answer exists
                         for that query at all (a natural negative). A natural
                         negative scores only on the negative arm: counting it as
                         a wrong positive would drag precision down for something
                         that is not the gate's fault.
      best_wrong_scores  the best score among candidates that are NOT gold, or
                         **None** when every returned candidate was gold, which
                         is skipped rather than scored.

    `fastpath_precision` is 0.0 rather than NaN when nothing is accepted -- the
    same choice `per_class_scores` makes, so the dict stays numeric and the table
    stays whole. It is vacuous there, `n_accepted` sits beside it, and it is
    deliberately not the headline.
    """
    if not (len(top_scores) == len(top_correct) == len(best_wrong_scores)):
        raise ValueError("top_scores, top_correct and best_wrong_scores must be "
                         "the same length")

    positives = [(s, bool(c)) for s, c in zip(top_scores, top_correct, strict=True)
                 if c is not None]
    negatives = [s for s in best_wrong_scores if s is not None]
    accepted = [c for s, c in positives if s >= tau]
    right = sum(1 for c in accepted if c)

    coverage_curve = coverage_accuracy_curve(
        [s for s, _ in positives], [c for _, c in positives], n_points=n_points,
    )
    return {
        "fastpath_aucc": area_under_coverage_curve(coverage_curve),
        "fastpath_coverage": len(accepted) / len(positives) if positives else 0.0,
        "fastpath_precision": right / len(accepted) if accepted else 0.0,
        "fastpath_yield": right / len(positives) if positives else 0.0,
        "false_accept_rate": (sum(1 for s in negatives if s >= tau) / len(negatives)
                              if negatives else 0.0),
        "tau": float(tau),
        "n": float(len(positives)),
        "n_accepted": float(len(accepted)),
        "n_negatives": float(len(negatives)),
        "n_natural_negatives": float(sum(1 for c in top_correct if c is None)),
        "n_skipped_no_wrong_candidate": float(
            sum(1 for s in best_wrong_scores if s is None)),
        "curve": fast_path_curve(top_scores, top_correct, best_wrong_scores,
                                 (*taus, tau)),
        "coverage_curve": coverage_curve,
    }


# -----------------------------------------------------------------------------
# Transliteration (FR-5)
# -----------------------------------------------------------------------------
# Character error rate is the metric the transliteration literature reports, so
# ours has to be comparable with published Dakshina numbers rather than
# something invented here. WER is kept beside it because a transliterator can
# have a respectable CER while getting most whole words wrong, and a user reads
# words.


def _levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    """Edit distance over any sequence -- characters for CER, words for WER."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, item_a in enumerate(a, start=1):
        current = [i]
        for j, item_b in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,                                  # deletion
                current[j - 1] + 1,                               # insertion
                previous[j - 1] + (item_a != item_b),             # substitution
            ))
        previous = current
    return previous[-1]


def _rate(hypotheses: Sequence[str], references: Sequence[str], *, words: bool) -> float:
    """Corpus-level error rate: total edits / total reference length.

    Corpus-level, NOT the mean of per-sentence rates. Averaging per-sentence
    rates lets a three-character reference weigh as much as a 200-character one,
    which on a set with wildly uneven lengths is a different and much noisier
    number than the one papers report.
    """
    edits = length = 0
    for hyp, ref in zip(hypotheses, references, strict=True):
        h = hyp.split() if words else list(hyp)
        r = ref.split() if words else list(ref)
        edits += _levenshtein(h, r)
        length += len(r)
    return edits / length if length else 0.0


def transliteration_metrics(
    hypotheses: Sequence[str], references: Sequence[str],
) -> dict[str, float]:
    """CER, WER and exact match. Lower is better for the first two."""
    if not references:
        return {"cer": 0.0, "wer": 0.0, "exact_match": 0.0, "n": 0.0}
    exact = sum(1 for h, r in zip(hypotheses, references, strict=True) if h.strip() == r.strip())
    return {
        "cer": _rate(hypotheses, references, words=False),
        "wer": _rate(hypotheses, references, words=True),
        "exact_match": exact / len(references),
        "n": float(len(references)),
    }


# -----------------------------------------------------------------------------
# Claim spans (FR-7)
# -----------------------------------------------------------------------------
# Token-level F1 over the claim tokens, which is what PRD 8 asks for and what
# the X-CLAIM paper reports. `O` is not a class here: it is the absence of one.
# Scoring O as a third class would let a model that predicts O everywhere score
# well on a post that is mostly not a claim, and about half of every X-CLAIM
# post is not.


def span_metrics(
    predicted: Sequence[Sequence[str]], reference: Sequence[Sequence[str]],
) -> dict[str, float]:
    """Token P/R/F1 over claim tokens, plus whole-span exact match.

    Corpus-level, not the mean of per-post F1s. A three-token post and a
    two-hundred-token one are different amounts of evidence, and averaging
    per-post rates would weigh them the same.
    """
    if not reference:
        return {"token_precision": 0.0, "token_recall": 0.0, "token_f1": 0.0,
                "exact_span_match": 0.0, "n": 0.0}

    tp = fp = fn = exact = 0
    for hyp, ref in zip(predicted, reference, strict=True):
        # A length mismatch means the prediction is not aligned to the same
        # tokenisation as the gold, which makes every position meaningless.
        if len(hyp) != len(ref):
            raise ValueError(
                f"span prediction has {len(hyp)} tags but gold has {len(ref)}. "
                "Predictions must be one tag per gold token."
            )
        hyp_claim = [t != "O" for t in hyp]
        ref_claim = [t != "O" for t in ref]
        tp += sum(1 for h, r in zip(hyp_claim, ref_claim) if h and r)
        fp += sum(1 for h, r in zip(hyp_claim, ref_claim) if h and not r)
        fn += sum(1 for h, r in zip(hyp_claim, ref_claim) if not h and r)
        exact += hyp_claim == ref_claim

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"token_precision": precision, "token_recall": recall, "token_f1": f1,
            "exact_span_match": exact / len(reference), "n": float(len(reference))}


# -----------------------------------------------------------------------------
# Claim normalization (FR-7)
# -----------------------------------------------------------------------------
# chrF rather than METEOR, which is what the CheckThat! shared task reports.
# METEOR's synonym matching runs through WordNet and is English-only, so an
# English METEOR and a Punjabi METEOR are not the same measurement and must not
# share a column. chrF is character n-gram F-score: language-agnostic, standard
# for multilingual generation, and short enough to verify by hand.


def _char_ngrams(text: str, n: int) -> Counter[str]:
    stripped = "".join(text.split())
    return Counter(stripped[i:i + n] for i in range(len(stripped) - n + 1))


def chrf(hypothesis: str, reference: str, max_n: int = 6, beta: float = 2.0) -> float:
    """chrF with recall weighted `beta` times precision (the standard beta=2)."""
    precisions, recalls = [], []
    for n in range(1, max_n + 1):
        hyp_grams, ref_grams = _char_ngrams(hypothesis, n), _char_ngrams(reference, n)
        overlap = sum((hyp_grams & ref_grams).values())
        hyp_total, ref_total = sum(hyp_grams.values()), sum(ref_grams.values())
        # An order with no n-grams on either side is skipped, not scored zero:
        # a 3-character reference has no 6-grams, and counting that as a miss
        # would punish short references for being short.
        if hyp_total:
            precisions.append(overlap / hyp_total)
        if ref_total:
            recalls.append(overlap / ref_total)
    if not precisions or not recalls:
        return 0.0
    avg_p = sum(precisions) / len(precisions)
    avg_r = sum(recalls) / len(recalls)
    if avg_p + avg_r == 0:
        return 0.0
    beta_sq = beta ** 2
    return (1 + beta_sq) * avg_p * avg_r / (beta_sq * avg_p + avg_r)


def normalization_metrics(
    hypotheses: Sequence[str], references: Sequence[str],
) -> dict[str, float]:
    """chrF and exact match. Higher is better for both."""
    if not references:
        return {"chrf": 0.0, "exact_match": 0.0, "n": 0.0}
    scores = [chrf(h, r) for h, r in zip(hypotheses, references, strict=True)]
    exact = sum(1 for h, r in zip(hypotheses, references, strict=True)
                if h.strip() == r.strip())
    return {"chrf": sum(scores) / len(scores),
            "exact_match": exact / len(references),
            "n": float(len(references))}


def word_faithfulness_metrics(drop_top: Sequence[float], drop_random: Sequence[float],
                              drop_bottom: Sequence[float], *, win_rate_bar: float = 0.80,
                              ratio_bar: float = 2.0, n_boot: int = 1000, seed: int = 42) -> dict[str, Any]:
    """The three gates of docs/word-highlight-protocol.md, over per-claim probability drops.

    drop_*: for each claim, the fall in P(verdict) when the 3 top words / 3 random words (already
    averaged over draws) / 3 bottom words are deleted. The word view ships only if all three gates hold.
    """
    n = len(drop_top)
    if not (n == len(drop_random) == len(drop_bottom)) or n == 0:
        raise ValueError("drop_top, drop_random and drop_bottom must be the same non-zero length")
    import numpy as np

    top, rnd, bot = (np.asarray(x, dtype=float) for x in (drop_top, drop_random, drop_bottom))
    wins = int((top > rnd).sum())
    mean_top, mean_rnd, mean_bot = float(top.mean()), float(rnd.mean()), float(bot.mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    diffs = (top - rnd)[idx].mean(axis=1)
    ratio = mean_top / mean_rnd if mean_rnd > 0 else float("inf")
    gates = {"win_rate": wins / n >= win_rate_bar, "mean_ratio": ratio >= ratio_bar,
             "bottom_not_above_random": mean_bot <= mean_rnd}
    return {
        "n": n, "wins": wins, "win_rate": wins / n, "mean_drop_top": mean_top,
        "mean_drop_random": mean_rnd, "mean_drop_bottom": mean_bot, "mean_ratio": ratio,
        "mean_diff_ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
        "gates": gates, "passes": all(gates.values()),
    }


def careful_rule_metrics(true_fired: Sequence[bool], false_fired: Sequence[bool], baseline_true_fired: Sequence[bool],
                         hoax_fired: Sequence[bool], *, max_false_warning: float = 0.15, max_vs_baseline: float = 0.5,
                         min_false_recall: float = 0.15, min_hoaxes: int = 20) -> dict[str, Any]:
    """The gates of docs/careful-rule-protocol.md. Each argument is a list of "did the rule caution this message".

    true_fired: the rule on true claims; baseline_true_fired: the rule it replaces on the same claims;
    false_fired: the rule on false claims; hoax_fired: on the 30 typical hoaxes (illustrative, but a gate).
    """
    if not true_fired or not false_fired or not hoax_fired or len(true_fired) != len(baseline_true_fired):
        raise ValueError("careful_rule_metrics needs non-empty sets and a baseline for every true claim")
    n_t, k_t = len(true_fired), sum(true_fired)
    k_b = sum(baseline_true_fired)
    n_f, k_f = len(false_fired), sum(false_fired)
    lo, hi = wilson_interval(k_t, n_t)
    rate_t, rate_b, rate_f = k_t / n_t, k_b / n_t, k_f / n_f
    gates = {
        "false_warning_rate": rate_t <= max_false_warning,
        "at_most_half_of_baseline": rate_t <= max_vs_baseline * rate_b,
        "false_claim_recall": rate_f >= min_false_recall,
        "typical_hoaxes": sum(hoax_fired) >= min_hoaxes,
    }
    return {"true_n": n_t, "true_cautioned": k_t, "true_rate": rate_t, "true_wilson95": [lo, hi],
            "baseline_true_rate": rate_b, "false_n": n_f, "false_cautioned": k_f, "false_rate": rate_f,
            "hoaxes_n": len(hoax_fired), "hoaxes_cautioned": int(sum(hoax_fired)),
            "gates": gates, "passes": all(gates.values())}


def real_claims_metrics(rows: Sequence[dict[str, Any]], *, min_precision: float = 0.85, min_precision_lower: float = 0.80,
                        max_false_supported_upper: float = 0.08) -> dict[str, Any]:
    """The numbers and the transfer rule of docs/real-claims-protocol.md.

    Each row: {"gold": "T"|"F"|"U", "shown": None|"Supported"|"Refuted", "decider": "factcheck"|"wikipedia"|None}.
    A verdict is correct when Supported meets T or Refuted meets F; a verdict on a U claim is counted separately.
    """
    def block(rs: Sequence[dict[str, Any]]) -> dict[str, Any]:
        n = len(rs)
        shown = [r for r in rs if r["shown"] in ("Supported", "Refuted")]
        decidable = [r for r in shown if r["gold"] in ("T", "F")]
        correct = sum(1 for r in decidable if (r["shown"] == "Supported") == (r["gold"] == "T"))
        gold_f = [r for r in rs if r["gold"] == "F"]
        fs = sum(1 for r in gold_f if r["shown"] == "Supported")
        p_lo, p_hi = wilson_interval(correct, len(decidable)) if decidable else (0.0, 1.0)
        f_lo, f_hi = wilson_interval(fs, len(gold_f)) if gold_f else (0.0, 1.0)
        return {"n": n, "shown": len(shown), "coverage": len(shown) / n if n else 0.0,
                "decidable_shown": len(decidable), "correct": correct,
                "precision": correct / len(decidable) if decidable else None, "precision_wilson95": [p_lo, p_hi],
                "gold_false": len(gold_f), "false_supported": fs,
                "false_supported_rate": fs / len(gold_f) if gold_f else None, "false_supported_wilson95": [f_lo, f_hi],
                "shown_on_unverifiable": sum(1 for r in shown if r["gold"] == "U")}

    out = {"all": block(rows), "by_decider": {d: block([r for r in rows if r["decider"] == d])
                                              for d in ("factcheck", "wikipedia")}}
    a = out["all"]
    ok_p = a["precision"] is not None and a["precision"] >= min_precision and a["precision_wilson95"][0] >= min_precision_lower
    ok_f = a["false_supported_wilson95"][1] <= max_false_supported_upper
    out["transfers"] = "transfers" if ok_p and ok_f else ("partly transfers" if ok_p or ok_f else "does not transfer")
    return out


def _is_correct(gold: str, shown: str | None) -> bool:
    return shown is not None and gold in ("T", "F") and (shown == "Supported") == (gold == "T")


def paired_flip_counts(plain: dict[str, tuple[str, str | None]], chatty: dict[str, tuple[str, str | None]]) -> dict[str, int]:
    """The same claims shown plain and wrapped in a chatty forward: id -> (gold, shown verdict or None).

    Counts how the shown verdict moves (docs/real-claims-protocol.md, RC-B against RC-C): both silent, silent to shown,
    shown to silent, same verdict, and verdict flipped (Supported <-> Refuted), plus how many shown verdicts are correct in each.
    """
    ids = sorted(set(plain) & set(chatty))
    out = {"n": len(ids), "both_silent": 0, "silent_to_shown": 0, "shown_to_silent": 0, "same_verdict": 0, "flipped": 0,
           "plain_correct": 0, "chatty_correct": 0}
    for i in ids:
        (g, a), (_, b) = plain[i], chatty[i]
        out["plain_correct"] += _is_correct(g, a)
        out["chatty_correct"] += _is_correct(g, b)
        if a is None and b is None:
            out["both_silent"] += 1
        elif a is None:
            out["silent_to_shown"] += 1
        elif b is None:
            out["shown_to_silent"] += 1
        elif a == b:
            out["same_verdict"] += 1
        else:
            out["flipped"] += 1
    return out

