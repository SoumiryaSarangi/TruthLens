"""No fast path in Phase 1.

The claim-matching track is Phase 4 and depends on MultiClaim access. Until
then every claim takes the evidence path, and the orchestrator records the
absence as a degradation so a trace never silently implies a fast path was
tried and missed.
"""

from __future__ import annotations

from pipeline.contracts import Claim, FactCheckMatch


class NoMatcher:
    name = "matching"
    impl = "none"
    note = "degraded: no fast path (matcher arrives in Phase 4)"

    def top1(self, claim: Claim) -> FactCheckMatch | None:
        return None
