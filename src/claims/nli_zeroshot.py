"""Zero-shot check-worthiness via the multilingual NLI model (FR-6).

The control arm the Phase 3 plan asked for, and -- after FR-6 failed -- the
approach most likely to work.

## Why this arm matters more than it did when it was planned

It was planned as the control for "is the trained classifier learning anything
the NLI model did not already know". Then the trained classifier caught **0 of
15** real no-claim messages, and the diagnosis was structural: it trains on
`xclaim_cw`, whose negatives are out-of-span REMAINDERS of posts that did
contain a claim, so it learned a distribution in which almost everything is
check-worthy and the negatives read as truncated mid-thought.

A zero-shot NLI model has no training distribution of ours to be skewed by. It
was trained on XNLI, where the question "does this text assert that?" is the
whole task. So it is the one approach whose failure mode is not the failure
mode that sank the trained arm -- which is the entire argument for running it.

## What it actually does

The Phase 1 stance model, unchanged, with the hypothesis pinned:

    premise     the forwarded message
    hypothesis  "This message states a fact that can be checked."
    Yes         P(entailment) >= THRESHOLD

`NLIStance` is reused rather than reimplemented, so this arm inherits its
label-order check -- the id2label map is read from the model's own config, and
a model whose labels were ordered differently would raise rather than silently
invert every decision.

## Two limitations to state rather than discover

- **The hypothesis is English and much of the input is not.** mDeBERTa-XNLI is
  multilingual and cross-lingual premise/hypothesis pairs are within its
  training distribution, but romanized Hindi and Punjabi are not: XNLI's Hindi
  is Devanagari. Whatever this arm scores on the romanized hand-typed set is a
  floor for the method, not its ceiling.
- **It only answers FR-6.** Extraction is delegated to the rules, because this
  arm exists to test one decision and mixing in a different extractor would
  make the comparison two changes wide.
"""

from __future__ import annotations

from pipeline.contracts import Trace

HYPOTHESIS = "This message states a fact that can be checked."

# P(entailment) at or above this is check-worthy. 0.5 is the untuned default and
# is what the reported number uses unless a config says otherwise; any other
# value is chosen on the DERIVED dev set, never on the hand-typed 100, which is
# the held-out report set for this requirement.
THRESHOLD = 0.5

# NLIStance maps NLI labels to stance names. Entailment arrives here as
# "Supports": the message supports the hypothesis that it states a checkable
# fact.
ENTAILMENT = "Supports"


def decide(probs: dict[str, float], threshold: float = THRESHOLD) -> bool:
    """The whole decision rule, as a pure function so it can be tested without a GPU.

    Thresholding P(entailment) rather than taking the argmax over all three NLI
    labels, because `neutral` is the argmax for most short texts and an argmax
    rule would answer "not check-worthy" to nearly everything -- which would tie
    the majority baseline from the opposite direction and measure nothing.
    """
    return probs.get(ENTAILMENT, 0.0) >= threshold


class NLIZeroShotClaims:
    """Check-worthiness with no fine-tuning at all. Rules for extraction."""

    name = "claims"
    impl = "nli"

    def __init__(self, hypothesis: str = HYPOTHESIS, threshold: float = THRESHOLD,
                 **kwargs: object) -> None:
        self.hypothesis = hypothesis
        self.threshold = float(threshold)
        self._kwargs = kwargs
        self._nli = None
        self._rules = None

    def _stance(self):
        if self._nli is None:
            from stance.nli import NLIStance
            self._nli = NLIStance(**self._kwargs)      # lazy: no torch at import
        return self._nli

    def _extractor(self):
        if self._rules is None:
            from claims.heuristic import HeuristicClaims
            self._rules = HeuristicClaims()
        return self._rules

    def probability(self, text: str) -> float:
        """P(entailment) that `text` states a checkable fact."""
        results = self._stance().label(self.hypothesis, [text])
        return results[0].probs.get(ENTAILMENT, 0.0) if results else 0.0

    def check_worthy(self, trace: Trace) -> bool:
        if not trace.pre or not trace.pre.normalized.strip():
            return False
        results = self._stance().label(self.hypothesis, [trace.pre.normalized])
        if not results:
            return False
        return decide(results[0].probs, self.threshold)

    def extract(self, trace: Trace) -> Trace:
        """Delegated to the rules. This arm is an FR-6 experiment, not an FR-7 one."""
        return self._extractor().extract(trace)
