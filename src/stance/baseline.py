"""The dumb stance baseline: everything is Neutral.

Registered because SYSTEM_DESIGN.md §3 requires every stage to have a baseline
and a model, and because it makes the aggregator's floor explicit -- all
Neutral means the rule aggregator returns NEI for every claim, which is exactly
the "never commits" system that any real stance model must beat.

Needs no weights, so tests can exercise the whole pipeline without a GPU.
"""

from __future__ import annotations

from stance.nli import StanceResult


class AlwaysNeutralStance:
    name = "stance"
    impl = "always_neutral"

    def __init__(self, **_: object):
        pass

    @property
    def loaded(self) -> bool:
        return True

    def load(self) -> None:
        return None

    def label(self, claim: str, passages: list[str]) -> list[StanceResult]:
        return [
            StanceResult("Neutral", 1.0,
                         {"Supports": 0.0, "Refutes": 0.0, "Neutral": 1.0})
            for _ in passages
        ]
