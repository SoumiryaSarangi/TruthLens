"""Runs the stages in order. SYSTEM_DESIGN.md §6.

The rule from §11: **degrade, record it, never crash, never make up a verdict.**
Every fallback here writes a note into `trace.events`, so a response can always
be read back to find out what actually ran.

Nothing in this module imports a model library. Stages are built through the
registry and import their own dependencies lazily.
"""

from __future__ import annotations

import concurrent.futures
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from pipeline import registry
from pipeline.contracts import MAX_CLAIMS, ClaimResult, Passage, Trace

# SYSTEM_DESIGN 11: "Generation error or over 8 s -> template explanation".
GENERATION_TIMEOUT_S = 8.0


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
    # FR-12: "zero passages, OR NONE ABOVE THE RELEVANCE FLOOR, yields NEI with
    # abstained = true". Only the first half existed until Phase 5. A dense
    # cosine is the only retrieval score here with an absolute scale -- BM25 is
    # unbounded and RRF is rank-based -- so the floor reads `dense_score`. Off by
    # default; chosen on dev by verdict macro-F1, like tau.
    relevance_floor: float | None = None
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
                "relevance_floor": self.relevance_floor,
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
        # A forward has no AVeriTeC pool, so free text needs its own retriever
        # over a global corpus (SYSTEM_DESIGN.md §14, D7). Optional and not in
        # DEFAULT_STAGES: an evaluation config never sees free text, and a
        # pipeline without it answers free text with an honest NEI.
        self.free_text_retriever = None
        if impl := s.get("free_text_retrieval"):
            self.free_text_retriever = registry.build(
                "retrieval", impl, **{**args.get("free_text_retrieval", {}), "k": cfg.k})
        self.stance = make("stance")
        self.aggregator = make("aggregate")
        # A learned aggregator reads ONE stance model's probabilities. Fed another
        # model's, it produces a confident distribution over noise and never
        # says so -- so the pairing is checked once, here, not trusted.
        trained_on = getattr(self.aggregator, "stance", None)
        if trained_on is not None and trained_on != s["stance"]:
            from pipeline.aggregate import AggregatorMismatch

            raise AggregatorMismatch(
                f"aggregate impl {s['aggregate']!r} was trained on stance "
                f"{trained_on!r} but this pipeline runs stance {s['stance']!r}."
            )
        self.generator = make("generation")
        self.faithfulness = make("faithfulness")
        # FR-18: the template always exists, whatever `generation` is set to.
        self.template = registry.build("generation", "template")
        self._gen_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

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
            return self._from_factcheck(trace, claim, match)

        # -- evidence path ----------------------------------------------------
        # An AVeriTeC claim is ranked within its own pool; free text goes to the
        # global demo corpus when the config names one.
        retriever = self.retriever if claim_idx is not None else self.free_text_retriever
        if retriever is None:
            # Say so rather than invent a verdict.
            trace.record("retrieval", self.retriever.impl, 0.0,
                         "degraded: no candidate pool for free-text input")
            return self._nei_abstain(claim, "No evidence corpus is available for "
                                            "free-text input.")

        try:
            scored = self._timed(trace, "retrieval", retriever.impl,
                                 lambda: retriever.topk(claim.text, claim_idx,
                                                        self.cfg.k))
        except Exception as exc:
            trace.record("retrieval", retriever.impl, 0.0,
                         f"degraded: retrieval failed ({type(exc).__name__})")
            scored = []

        # NFR-7: a hybrid retriever whose encoder failed returns BM25's ranking
        # and says so on the ranking it returns. Recorded here so the trace shows
        # that the evidence came from a weaker path than the config names.
        if note := getattr(scored, "note", None):
            trace.record("retrieval", retriever.impl, 0.0, note)

        if not scored:
            return self._nei_abstain(claim, "No sources were retrieved.")   # FR-12

        # Passage selection was outside any `try` until Phase 5, so a retriever
        # that failed there crashed `verify()` instead of degrading -- the one
        # thing SYSTEM_DESIGN 11 says must never happen. The lexical selector
        # needs no model, so it is the fallback.
        try:
            passages = self._to_passages(claim.text, scored, retriever=retriever)
        except Exception as exc:
            trace.record("retrieval", retriever.impl, 0.0,
                         f"degraded: passage selection failed ({type(exc).__name__}); "
                         "lexical paragraphs")
            passages = self._to_passages(claim.text, scored, lexical=True)

        # FR-12, the half that did not exist: sources were found, but none is
        # relevant enough to judge from. Abstaining here costs an NEI; reading
        # stance off irrelevant pages is what produced Phase 1's 3.7x
        # over-prediction of Conflicting.
        if self.cfg.relevance_floor is not None:
            dense = [s for sd in scored
                     if (s := getattr(sd, "dense_score", None)) is not None]
            if not dense:
                trace.record("retrieval", retriever.impl, 0.0,
                             "relevance floor not applied: this retriever gives "
                             "no dense score")
            elif max(dense) < self.cfg.relevance_floor:
                trace.record("retrieval", retriever.impl, 0.0,
                             f"no source above relevance floor ({max(dense):.3f} < "
                             f"{self.cfg.relevance_floor:.3f})")
                return self._nei_abstain(
                    claim, "No retrieved source was relevant enough to judge from.",
                    passages=passages)

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

        dense = [getattr(sd, "dense_score", None) for sd in scored][:len(probs)]
        agg = self._timed(trace, "aggregate", self.aggregator.impl,
                          lambda: self.aggregator.aggregate(probs, dense=dense))
        abstained = agg.confidence < self.cfg.tau_abstain          # FR-14

        explanation, cited, source, faith = self._explain(
            trace, claim.text, agg.verdict, passages, abstained)
        return ClaimResult(
            claim=claim, path="evidence", match=None, passages=passages,
            verdict=agg.verdict, confidence=agg.confidence, abstained=abstained,
            verdict_probs=getattr(agg, "probs", None),
            explanation=explanation, explanation_source=source,
            explanation_lang=("en" if source == "generated"
                              else trace.pre.lang if trace.pre else "en"),
            cited=cited, faithfulness=faith,
        )

    def _explain(self, trace: Trace, claim_text: str, verdict: str,
                 passages: list[Passage], abstained: bool):
        """Generated text only if every sentence passes the NLI gate (FR-15/16/18).

        Returns (explanation, cited, source, faithfulness). Every way generated
        text can fail -- abstained, timeout, error, no gate, an unentailed
        sentence -- falls back to the template, and each is recorded, because
        `explanation_source: template` alone cannot say WHY.
        """
        def template(note: str | None = None):
            if note:
                trace.record("generation", self.generator.impl, 0.0, note)
            text, cited = self.template.explain(verdict, passages, abstained=abstained)
            return text, cited, "template", None

        if self.generator.impl == "template":
            return template()
        if abstained:
            # SYSTEM_DESIGN 11: never fluent prose for an answer the system
            # declined to stand behind.
            return template("abstained: template explanation by rule")
        if not hasattr(self.faithfulness, "check"):
            return template(f"no faithfulness gate ({self.faithfulness.impl}); "
                            "generated text is never served ungated")

        t0 = time.perf_counter()
        future = self._gen_pool.submit(self.generator.explain, verdict, passages,
                                       claim=claim_text)
        try:
            raw, _ = future.result(timeout=GENERATION_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            return template(f"degraded: generation over {GENERATION_TIMEOUT_S:.0f} s; "
                            "template served")
        except Exception as exc:
            return template(f"degraded: generation failed ({type(exc).__name__}); "
                            "template served")
        trace.record("generation", self.generator.impl,
                     (time.perf_counter() - t0) * 1000)

        texts = [p.text for p in passages]
        try:
            check = self._timed(trace, "faithfulness", self.faithfulness.impl,
                                lambda: self.faithfulness.check(raw, texts))
        except Exception as exc:
            return template(f"degraded: faithfulness check failed "
                            f"({type(exc).__name__}); template served")
        if not check["faithful"]:
            weakest = min(check["entailment"]) if check["entailment"] else 0.0
            return template(f"faithfulness: generated explanation failed the NLI gate "
                            f"(weakest sentence entailment {weakest:.2f}); template served")
        cited_idx = sorted({j for js in check["supporting"] for j in js})
        return (raw, [passages[j].passage_id for j in cited_idx], "generated",
                min(check["entailment"]))

    # -- result constructors --------------------------------------------------
    def _to_passages(self, claim_text: str, scored, lexical: bool = False,
                     retriever=None) -> list[Passage]:
        if lexical:
            from retrieval.passages import best_paragraph as lexical_best

            def select(text, doc):
                return lexical_best(text, doc.paragraphs)
        else:
            select = (retriever or self.retriever).best_paragraph
        out: list[Passage] = []
        for i, sd in enumerate(scored, start=1):
            text, span = select(claim_text, sd.document)
            # An AVeriTeC document's id IS its URL; a demo-corpus document
            # carries its URL and title separately (`retrieval/corpus.py`).
            out.append(Passage(
                passage_id=f"e{i}", doc_id=sd.doc_id, text=text,
                url=getattr(sd.document, "url", None) or sd.doc_id,
                title=getattr(sd.document, "title", None) or None,
                retrieval_score=sd.score,
                highlight=span,
            ))
        return out

    def _nei_abstain(self, claim, why: str,
                     passages: list[Passage] | None = None) -> ClaimResult:
        """NEI, abstained. With `passages`, the sources that were looked at and
        judged too weak -- kept so the retrieval eval and the UI still see them."""
        return ClaimResult(
            claim=claim, path="evidence" if passages else "none", match=None,
            passages=passages or [],
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

    def _from_factcheck(self, trace: Trace, claim, match) -> ClaimResult:
        explanation = (f"Already checked by {match.publisher}: {match.title}")
        # `ClaimResult.confidence` is validated to [0, 1] and `match.score` is a
        # raw retrieval score. A cosine can be negative and a BM25 score is
        # unbounded -- measured around 20 on the fact-check pool -- so assigning
        # it straight through raised a ValidationError at request time. It was
        # unreachable only because `NoMatcher` never returned a match.
        #
        # Clamping keeps the response valid; it does NOT make the number a
        # confidence. It is an uncalibrated retrieval score wearing the field's
        # name, and the trace says so. Calibration is Phase 6 (FR-13, FR-14).
        confidence = min(max(float(match.score), 0.0), 1.0)
        if confidence != match.score:
            trace.record("matching", self.matcher.impl, 0.0,
                         f"fast-path score {match.score:.4f} clamped to "
                         f"{confidence:.4f} for the confidence field")
        trace.record("matching", self.matcher.impl, 0.0,
                     "fast-path confidence is an uncalibrated retrieval score")
        return ClaimResult(
            claim=claim, path="fast", match=match, passages=[],
            verdict=match.verdict, confidence=confidence, abstained=False,
            explanation=explanation, explanation_source="template",
            explanation_lang=match.lang, cited=[match.factcheck_id],
        )
