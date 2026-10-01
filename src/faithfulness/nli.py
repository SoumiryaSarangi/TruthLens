"""The faithfulness gate (FR-16): no generated sentence the evidence does not entail.

Every sentence of a generated explanation must be entailed (mDeBERTa XNLI,
P >= 0.5) by at least one of the passages shown with it. If any sentence fails,
the orchestrator serves the template instead and records the replacement --
fluent text that the evidence does not support is the failure a fact-checker
cannot afford.

The gate calls `eval.faithfulness.support`, the SAME function the harness grades
with, so "passed the gate" and "graded faithful" cannot mean different things.
Citations come from here too: a sentence cites the passages that entail it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class NLIFaithfulness:
    name = "faithfulness"
    impl = "nli"

    def check(self, explanation: str, evidence: Sequence[str]) -> dict[str, Any]:
        from eval.faithfulness import support

        return support(explanation, list(evidence))

    def restates(self, explanation: str, claim: str) -> float:
        """Highest P(sentence entails the claim) over the explanation's sentences.

        Faithfulness to the evidence is not enough. Found on a real forward: for
        "har student ko 6000 rupaye milenge" (verdict Refuted) the explainer
        returned the claim itself, word for word, and it passed the gate at 0.99
        because one retrieved passage asserted the rumour. Served, that is the
        rumour as the system's own explanation, under a Refuted verdict.
        """
        from eval.faithfulness import get_scorer, sentences

        sents = sentences(explanation)
        if not sents or not (claim or "").strip():
            return 0.0
        return max(get_scorer()([(s, claim) for s in sents]))

    def score(self, explanation: str, evidence: list[str]) -> float | None:
        """The weakest sentence's entailment: one unsupported sentence is the score."""
        result = self.check(explanation, evidence)
        return min(result["entailment"]) if result["entailment"] else 0.0
