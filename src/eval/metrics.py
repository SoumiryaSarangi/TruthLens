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
