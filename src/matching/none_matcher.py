"""The null matcher: every claim takes the evidence path.

Phase 1's only matcher, and from Phase 4 the BASELINE the real one is compared
against -- `SYSTEM_DESIGN.md` §3 requires every stage to have at least two
implementations by the phase that introduces its model, and `registry.py` says
which one runs is chosen by config and never by editing code.

It also stays the answer to `SYSTEM_DESIGN.md` §11's "matcher or index
unavailable": the orchestrator records the absence as a degradation, so a trace
never silently implies a fast path was tried and missed.
"""

from __future__ import annotations

from pipeline.contracts import Claim, FactCheckMatch


class NoMatcher:
    name = "matching"
    impl = "none"
    note = "degraded: no fast path (matching impl is `none`)"

    def __init__(self, **_: object) -> None:
        """Extra kwargs are absorbed, like every other stage implementation.

        Without this, switching `matching` to `none` in a config whose
        `stage_args.matching` still names a reranker or an encoder raised a
        TypeError from the registry -- i.e. changing an impl in YAML crashed the
        app, which is the exact failure the registry exists to prevent. Every
        retriever here already takes `**_`; this was the outlier.
        """

    def top1(self, claim: Claim) -> FactCheckMatch | None:
        return None
