"""Faithfulness of an explanation to its evidence, by NLI (FR-16, PRD metric).

CLAUDE.md defines the metric: *NLI entailment of the explanation w.r.t.
retrieved evidence.* Made precise here, once:

* An explanation is split into sentences; citation markers like `[2]` are
  removed first, because a marker is not a claim about the world.
* A sentence's support is its HIGHEST entailment probability over the evidence
  passages -- one passage that entails it is enough.
* An explanation is **faithful** iff it has at least one sentence and EVERY
  sentence clears `ENTAIL_THRESHOLD`. One unsupported sentence is exactly the
  failure the check exists for; averaging it away would hide it.

The grader is fixed here, not chosen by the pipeline config: mDeBERTa-v3 XNLI,
premise = passage, hypothesis = sentence. The pipeline's own gate
(`faithfulness/nli.py`) calls the same `support()` so the gate and the grade
cannot disagree about what "supported" means.

Imports torch lazily. Tests install a fake scorer with `set_scorer()`, so the
harness stays testable in CI, which has no torch.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

ENTAIL_THRESHOLD = 0.5
_CITATION = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\]")
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")

# (premise, hypothesis) pairs -> P(entailment) for each.
Scorer = Callable[[list[tuple[str, str]]], list[float]]
_SCORER: Scorer | None = None


def set_scorer(scorer: Scorer | None) -> None:
    """Install a scorer (tests), or None to fall back to the real NLI model."""
    global _SCORER
    _SCORER = scorer


def _default_scorer() -> Scorer:
    from stance.nli import NLIStance

    model = NLIStance()

    def score(pairs: list[tuple[str, str]]) -> list[float]:
        return [r.probs["Supports"] for r in model.score_pairs(pairs)]

    return score


def get_scorer() -> Scorer:
    global _SCORER
    if _SCORER is None:
        _SCORER = _default_scorer()
    return _SCORER


def sentences(text: str) -> list[str]:
    """Sentences of an explanation, citation markers removed."""
    clean = _CITATION.sub("", text or "").strip()
    return [s.strip() for s in _SENTENCE.split(clean) if s.strip()]


def support(explanation: str, evidence: Sequence[str],
            scorer: Scorer | None = None) -> dict[str, Any]:
    """Per-sentence support for one explanation.

    Returns the sentences, each one's best entailment and the passages (0-based)
    that clear the threshold for it -- which is what citations are made from.
    """
    sents = sentences(explanation)
    # Indices into the evidence AS GIVEN, so `supporting` can be turned straight
    # into citations; empty passages are skipped, not renumbered around.
    kept = [(j, p) for j, p in enumerate(evidence) if p and p.strip()]
    if not sents or not kept:
        return {"sentences": sents, "entailment": [0.0] * len(sents),
                "supporting": [[] for _ in sents], "faithful": False}
    scorer = scorer or get_scorer()
    pairs = [(p, s) for s in sents for _, p in kept]
    probs = scorer(pairs)
    width = len(kept)
    best, supporting = [], []
    for i in range(len(sents)):
        row = probs[i * width:(i + 1) * width]
        best.append(max(row))
        supporting.append([kept[c][0] for c, v in enumerate(row) if v >= ENTAIL_THRESHOLD])
    return {"sentences": sents, "entailment": best, "supporting": supporting,
            "faithful": all(v >= ENTAIL_THRESHOLD for v in best)}


def faithfulness_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Aggregate `support()` results. An empty explanation counts as unfaithful."""
    n = len(rows)
    if not n:
        return {"n": 0.0, "faithful_rate": 0.0, "mean_min_entailment": 0.0,
                "mean_sentence_entailment": 0.0, "n_sentences_mean": 0.0}
    mins = [min(r["entailment"]) if r["entailment"] else 0.0 for r in rows]
    flat = [v for r in rows for v in r["entailment"]]
    return {
        "n": float(n),
        "faithful_rate": sum(1 for r in rows if r["faithful"]) / n,
        "mean_min_entailment": sum(mins) / n,
        "mean_sentence_entailment": sum(flat) / len(flat) if flat else 0.0,
        "n_sentences_mean": sum(len(r["sentences"]) for r in rows) / n,
    }
