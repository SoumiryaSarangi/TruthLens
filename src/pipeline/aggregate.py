"""Stance over passages -> one verdict. SYSTEM_DESIGN.md §6.

The Phase 1 aggregator is a fixed rule, fully specified, so it is a real floor
rather than a tuned thing pretending to be one:

    max P(Supports) >= t and max P(Refutes) >= t   -> Conflicting
    max P(Supports) >= t                           -> Supported
    max P(Refutes)  >= t                           -> Refuted
    otherwise                                      -> NEI

Confidence is the winning probability. It is NOT calibrated -- Phase 6 replaces
this with a learned aggregator plus temperature scaling, and reports ECE before
and after. Until then, treat the number as a score, not a probability, and note
that abstention thresholds chosen against it mean little.

This stays registered as `aggregate_rule` after Phase 6 so the improvement is
measurable rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_THRESHOLD = 0.5


@dataclass(frozen=True)
class Aggregated:
    verdict: str
    confidence: float
    max_supports: float
    max_refutes: float


class RuleAggregator:
    name = "aggregate"
    impl = "rule"

    def __init__(self, threshold: float = DEFAULT_THRESHOLD, **_: object):
        self.threshold = threshold

    def aggregate(self, stance_probs: list[dict[str, float]]) -> Aggregated:
        """`stance_probs` is one dict per retrieved passage."""
        if not stance_probs:
            # FR-12: no evidence is not a verdict. The caller also marks it
            # abstained; returning NEI here keeps that decision in one place.
            return Aggregated("NEI", 0.0, 0.0, 0.0)

        sup = max(p.get("Supports", 0.0) for p in stance_probs)
        ref = max(p.get("Refutes", 0.0) for p in stance_probs)
        t = self.threshold

        if sup >= t and ref >= t:
            return Aggregated("Conflicting", max(sup, ref), sup, ref)
        if sup >= t:
            return Aggregated("Supported", sup, sup, ref)
        if ref >= t:
            return Aggregated("Refuted", ref, sup, ref)

        # Nothing was confident either way. Confidence is how strongly the
        # evidence declined to commit, which is what an abstention threshold
        # should later be applied to.
        return Aggregated("NEI", 1.0 - max(sup, ref), sup, ref)
