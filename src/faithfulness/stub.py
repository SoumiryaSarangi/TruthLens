"""Faithfulness checking is Phase 6.

Returns None rather than a number. A stub that returned 1.0 would put a
confident-looking score in every results JSON for a check that never ran, and
somebody would eventually report it.
"""

from __future__ import annotations


class StubFaithfulness:
    name = "faithfulness"
    impl = "stub"

    def score(self, explanation: str, evidence: list[str]) -> float | None:
        return None
