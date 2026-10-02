"""Two stance models, two jobs: NLI labels the passages, both inform the verdict.

Phase 6 measured that the stance models are good at different things:

* **XLM-R gives the better verdict** -- macro-F1 0.2802 against NLI's 0.2135 on
  AVeriTeC dev, +0.067 with a 95% CI of [+0.022, +0.112] -- but it labels almost
  every passage "Refutes" whatever the passage says (Phase 5 and Phase 6 demo
  forwards): its signal is the claim, not the evidence.
* **NLI's per-passage labels are honest** (10/10 Delhi leads support "Delhi is
  India's capital") but its verdict is significantly worse.

The user SEES the per-passage labels -- the template explanation reads
"[2] <title> contradicts it" -- so showing XLM-R's would state that passages
contradict a claim they say nothing about. This stage therefore returns NLI's
label for display and carries BOTH models' distributions for the aggregator:
NLI's under the plain keys, XLM-R's under `xlmr:`-prefixed keys. Which of them
the learned aggregator reads is recorded in its artifact (`sources`).
"""

from __future__ import annotations

from stance.nli import NLIStance, StanceResult
from stance.xlmr import XLMRStance

PREFIX = "xlmr:"


class CombinedStance:
    name = "stance"
    impl = "xlmr_nli"

    def __init__(self, batch_size: int = 16, **kwargs: object) -> None:
        self.nli = NLIStance(batch_size=batch_size)
        adapter = kwargs.get("adapter")
        self.xlmr = XLMRStance(adapter=adapter) if adapter else XLMRStance()

    def label(self, claim: str, passages: list[str]) -> list[StanceResult]:
        if not passages:
            return []
        shown = self.nli.label(claim, passages)
        prior = self.xlmr.label(claim, passages)
        return [
            StanceResult(n.stance, n.prob,
                         {**n.probs, **{PREFIX + k: v for k, v in x.probs.items()}})
            for n, x in zip(shown, prior, strict=True)
        ]
