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


def classification_metrics(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str],
) -> dict[str, Any]:
    return {
        "n": float(len(y_true)),
        "accuracy": accuracy(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred, labels),
        "per_class": per_class_scores(y_true, y_pred, labels),
        "confusion": confusion_matrix(y_true, y_pred, labels),
    }


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
