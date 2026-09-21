"""Phase 1 claim handling: the whole input is one claim.

No check-worthiness filter and no span extraction -- both are Phase 3, and both
register their own implementations beside this one. The consequence for Phase 1
metrics is worth stating: `NotAClaim` is never predicted, so its per-class F1
is 0 and macro-F1 over the 5-class scheme is capped accordingly. That is the
documented, expected shape of a Phase 1 number, not a bug.
"""

from __future__ import annotations

from pipeline.contracts import Claim, Trace

MAX_CLAIMS = 3          # FR-7


class PassthroughClaims:
    name = "claims"
    impl = "passthrough"

    def check_worthy(self, trace: Trace) -> bool:
        """Everything is check-worthy in Phase 1. Real filter: Phase 3, FR-6."""
        return bool(trace.pre and trace.pre.normalized.strip())

    def extract(self, trace: Trace) -> Trace:
        assert trace.pre is not None
        trace.claims = [Claim(claim_id="c1", text=trace.pre.normalized, span=None)]
        trace.unchecked_claims = []
        return trace
