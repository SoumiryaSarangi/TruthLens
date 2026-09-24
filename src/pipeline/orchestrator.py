"""Runs the stages in order. SYSTEM_DESIGN.md §6.

The rule from §11: **degrade, record it, never crash, never make up a verdict.**
Every fallback here writes a note into `trace.events`, so a response can always
be read back to find out what actually ran.

Nothing in this module imports a model library. Stages are built through the
registry and import their own dependencies lazily.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from pipeline import registry
from pipeline.contracts import MAX_CLAIMS, ClaimResult, Passage, Trace


@dataclass
class PipelineConfig:
    """Which implementation runs at each stage, plus thresholds.

    τ values live here rather than in code so they can be chosen on dev and
    reported by `GET /version` (FR-14).
    """

    name: str = "dev"
    split: str = "dev"
    k: int = 10
    tau_match: float = 0.0
    tau_abstain: float = 0.0
    stages: dict[str, str] | None = None
    stage_args: dict[str, dict[str, Any]] | None = None

    DEFAULT_STAGES: ClassVar[dict[str, str]] = {
        "preprocess": "passthrough",
        "claims": "passthrough",
        "matching": "none",
        "retrieval": "bm25",
        "stance": "nli",
        "aggregate": "rule",
        "generation": "template",
        "faithfulness": "stub",
    }

    def __post_init__(self) -> None:
        self.stages = {**self.DEFAULT_STAGES, **(self.stages or {})}
        self.stage_args = self.stage_args or {}

    @classmethod
    def load(cls, path: str | Path) -> PipelineConfig:
        with Path(path).open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return cls(**raw)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "split": self.split, "k": self.k,
                "tau_match": self.tau_match, "tau_abstain": self.tau_abstain,
                "stages": dict(self.stages or {})}


class Orchestrator:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        s = cfg.stages or {}
        args = cfg.stage_args or {}

        def make(stage: str, **extra):
            return registry.build(stage, s[stage], **{**args.get(stage, {}), **extra})

        self.preprocess = make("preprocess")
        self.claims = make("claims")
        self.matcher = make("matching")
        self.retriever = make("retrieval", split=cfg.split, k=cfg.k)
        self.stance = make("stance")
        self.aggregator = make("aggregate")
        self.generator = make("generation")
        self.faithfulness = make("faithfulness")

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _timed(trace: Trace, stage: str, impl: str, fn, note: str | None = None):
        t0 = time.perf_counter()
        out = fn()
        trace.record(stage, impl, (time.perf_counter() - t0) * 1000, note)
        return out

    # -- the flow -------------------------------------------------------------
    def verify(self, text: str, claim_idx: int | None = None) -> Trace:
        trace = Trace(request_id=uuid.uuid4().hex[:12])

        self._timed(trace, "preprocess", self.preprocess.impl,
                    lambda: self.preprocess.run(trace, text))
        assert trace.pre is not None

        if trace.pre.lang == "other":
            trace.record("orchestrator", "-", 0.0, "unsupported language")
            return trace

        trace.checkworthy = self._timed(trace, "claims", self.claims.impl,
                                        lambda: self.claims.check_worthy(trace))
        if not trace.checkworthy:
            trace.results.append(self._not_a_claim(trace))       # FR-6
            return trace

        self._timed(trace, "claims", self.claims.impl, lambda: self.claims.extract(trace))

        # FR-7: at most MAX_CLAIMS are verified; the rest are LISTED as not
        # checked. Enforced here rather than trusted to the extractor, because
        # "at most 3" is a promise the API makes to the user and every future
        # claims implementation would otherwise have to remember to keep it.
        # Each extra claim costs a full retrieval and NLI pass, so an extractor
        # that over-produces is expensive as well as wrong.
        if len(trace.claims) > MAX_CLAIMS:
            overflow = trace.claims[MAX_CLAIMS:]
            trace.claims = trace.claims[:MAX_CLAIMS]
            trace.unchecked_claims = [c.text for c in overflow] + trace.unchecked_claims
            trace.record("claims", self.claims.impl, 0.0,
                         f"capped at {MAX_CLAIMS} claims; {len(overflow)} listed unchecked")

        for claim in trace.claims:
            trace.results.append(self._verify_claim(trace, claim, claim_idx))
        return trace

    def _verify_claim(self, trace: Trace, claim, claim_idx: int | None) -> ClaimResult:
        # -- fast path (Phase 4; `none` matcher always misses) -----------------
        match = self._timed(trace, "matching", self.matcher.impl,
                            lambda: self.matcher.top1(claim),
                            getattr(self.matcher, "note", None))
        if match is not None and match.score >= self.cfg.tau_match:
            return self._from_factcheck(claim, match)

        # -- evidence path ----------------------------------------------------
        if claim_idx is None:
            # No candidate pool: Phase 1 retrieval is per AVeriTeC claim, so a
            # free-text request has nothing to search until the demo corpus
            # exists (SYSTEM_DESIGN.md §7). Say so rather than invent a verdict.
            trace.record("retrieval", self.retriever.impl, 0.0,
                         "degraded: no candidate pool for free-text input")
            return self._nei_abstain(claim, "No evidence corpus is available for "
                                            "free-text input yet.")

        try:
            scored = self._timed(trace, "retrieval", self.retriever.impl,
                                 lambda: self.retriever.topk(claim.text, claim_idx,
                                                             self.cfg.k))
        except Exception as exc:
            trace.record("retrieval", self.retriever.impl, 0.0,
                         f"degraded: retrieval failed ({type(exc).__name__})")
            scored = []

        if not scored:
            return self._nei_abstain(claim, "No sources were retrieved.")   # FR-12

        passages = self._to_passages(claim.text, scored)

        # -- stance -----------------------------------------------------------
        try:
            results = self._timed(trace, "stance", self.stance.impl,
                                  lambda: self.stance.label(claim.text,
                                                            [p.text for p in passages]))
        except Exception as exc:
            trace.record("stance", self.stance.impl, 0.0,
                         f"degraded: stance failed ({type(exc).__name__}); treating as Neutral")
            results = []

        probs: list[dict[str, float]] = []
        for passage, res in zip(passages, results):
            passage.stance = res.stance
            passage.stance_prob = res.prob
            probs.append(res.probs)

        agg = self._timed(trace, "aggregate", self.aggregator.impl,
                          lambda: self.aggregator.aggregate(probs))
        abstained = agg.confidence < self.cfg.tau_abstain          # FR-14

        explanation, cited = self.generator.explain(agg.verdict, passages,
                                                    abstained=abstained)
        return ClaimResult(
            claim=claim, path="evidence", match=None, passages=passages,
            verdict=agg.verdict, confidence=agg.confidence, abstained=abstained,
            explanation=explanation, explanation_source="template",
            explanation_lang=trace.pre.lang if trace.pre else "en",
            cited=cited,
            faithfulness=self.faithfulness.score(explanation, [p.text for p in passages]),
        )

    # -- result constructors --------------------------------------------------
    def _to_passages(self, claim_text: str, scored) -> list[Passage]:
        out: list[Passage] = []
        for i, sd in enumerate(scored, start=1):
            text, span = self.retriever.best_paragraph(claim_text, sd.document)
            out.append(Passage(
                passage_id=f"e{i}", doc_id=sd.doc_id, text=text,
                url=sd.doc_id, title=None, retrieval_score=sd.score,
                highlight=span,
            ))
        return out

    def _nei_abstain(self, claim, why: str) -> ClaimResult:
        return ClaimResult(
            claim=claim, path="none", match=None, passages=[],
            verdict="NEI", confidence=0.0, abstained=True,
            explanation=f"There is not enough evidence to judge this claim. {why}",
            explanation_source="template", explanation_lang="en", cited=[],
        )

    def _not_a_claim(self, trace: Trace) -> ClaimResult:
        from pipeline.contracts import Claim

        text = trace.pre.normalized if trace.pre else ""
        return ClaimResult(
            claim=Claim(claim_id="c1", text=text), path="none", match=None,
            passages=[], verdict="NotAClaim", confidence=1.0, abstained=False,
            explanation="There is no checkable factual claim here.",
            explanation_source="template", explanation_lang="en", cited=[],
        )

    def _from_factcheck(self, claim, match) -> ClaimResult:
        explanation = (f"Already checked by {match.publisher}: {match.title}")
        return ClaimResult(
            claim=claim, path="fast", match=match, passages=[],
            verdict=match.verdict, confidence=match.score, abstained=False,
            explanation=explanation, explanation_source="template",
            explanation_lang=match.lang, cited=[match.factcheck_id],
        )
