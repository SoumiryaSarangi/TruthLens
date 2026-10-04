"""Runs the stages in order. SYSTEM_DESIGN.md §6.

The rule from §11: **degrade, record it, never crash, never make up a verdict.**
Every fallback here writes a note into `trace.events`, so a response can always
be read back to find out what actually ran.

Nothing in this module imports a model library. Stages are built through the
registry and import their own dependencies lazily.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from pipeline import registry
from pipeline.contracts import MAX_CLAIMS, Claim, ClaimResult, Passage, Trace

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
    # Free text only (post-test, Phase 7), both off by default so no evaluation
    # config changes. `free_text_translit_query`: search romanized hi/pa with
    # the claim AND its native-script transliteration -- the claim text itself
    # stays in Latin letters, so without this the Hindi/Punjabi corpus is
    # searched in the wrong script. `free_text_coverage`: abstain when no
    # passage contains this share of the claim's content words
    # (pipeline/relevance.py).
    free_text_translit_query: bool = False
    free_text_coverage: float | None = None
    # Post-test Phase 7: live Wikipedia + Google Fact Check, only when a request
    # asks (`verify(..., live=True)`), only for free text, only for the claim sent.
    # Off by default: no evaluation config can reach the network.
    live_search: bool = False
    # What live evidence may do. False (the default, and what is served): the card
    # lists the relevant sources and gives NO verdict -- no NLI label ever reaches
    # the user, so a false claim cannot be called Supported by a model misreading
    # Hindi (probe run 1, docs/live-search-probe.md). True: the verdict path built
    # for the probe, adopted only if a fix passes the same rule on a fresh set.
    live_verdict: bool = False
    # Offer the best fact-check below tau_match as "a fact-checker looked at something similar" (a
    # suggestion, never a verdict). None = off. Chosen on dev by docs/similar-factcheck-protocol.md.
    tau_similar: float | None = None
    # Route A of the live verdict (post-test Phase 7): translate a hi/pa claim to
    # English, search English Wikipedia too, and run the NLI in English. Only
    # meaningful with live_verdict. Left out of describe() unless on, so no
    # existing config hash moves.
    live_translate: bool = False
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
        out = {"name": self.name, "split": self.split, "k": self.k,
               "tau_match": self.tau_match, "tau_abstain": self.tau_abstain,
               "relevance_floor": self.relevance_floor,
               "free_text_translit_query": self.free_text_translit_query,
               "free_text_coverage": self.free_text_coverage,
               "live_search": self.live_search,
               "live_verdict": self.live_verdict,
               "stages": dict(self.stages or {})}
        if self.live_translate:
            out["live_translate"] = True
        if self.tau_similar is not None:
            out["tau_similar"] = self.tau_similar
        return out


LIVE_NLI_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
LIVE_PARTNER_MODEL = "facebook/bart-large-mnli"


def _translator_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


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
        # The stance impl is passed so a learned aggregator finds the artifact
        # trained for it (`aggregator_<stance>`) when no explicit path is set.
        self.aggregator = make("aggregate", stance=s["stance"])
        # A learned aggregator reads ONE stance model's probabilities. Fed another
        # model's, it produces a confident distribution over noise and never
        # says so -- so the pairing is checked once, here, not trusted.
        # Checked only when the artifact exists: a missing one degrades to the
        # rule at aggregation time (below) rather than refusing to start.
        trained_on = (getattr(self.aggregator, "stance", None)
                      if getattr(self.aggregator, "available", True) else None)
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
        # FR-19, optional: absent means no flags, as for every evaluation config.
        self.manipulation = registry.build(
            "manipulation", s.get("manipulation", "none"), **args.get("manipulation", {}))
        self._gen_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._live_capture: list | None = None   # a harness may set this to record the NLI inputs
        self._live_partner_nli = None
        self._live_init = threading.RLock()   # the warm-up thread and a request may both ask
        self._live_nli = None       # English NLI for the live verdict, built on first use
        self._translator = None     # NLLB, loaded on the first translated live request
        self._live = None           # built on the first live request, never otherwise

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _timed(trace: Trace, stage: str, impl: str, fn, note: str | None = None):
        t0 = time.perf_counter()
        out = fn()
        trace.record(stage, impl, (time.perf_counter() - t0) * 1000, note)
        return out

    # -- the flow -------------------------------------------------------------
    def verify(self, text: str, claim_idx: int | None = None, live: bool = False,
               force_claim: bool = False) -> Trace:
        trace = self._decide(text, claim_idx, force_claim)
        if live:
            self._apply_live(trace, claim_idx)
        # FR-19: flags are computed only AFTER every verdict is decided and are
        # copied onto the results, so no flag can move a verdict, a confidence
        # or an abstention. A failing flagger degrades to no flags (NFR-7).
        if trace.results and trace.pre is not None:
            try:
                flags = self._timed(
                    trace, "manipulation", self.manipulation.impl,
                    lambda: self.manipulation.flags(trace.pre.original,
                                                    trace.pre.transliterated))
            except Exception as exc:
                trace.record("manipulation", self.manipulation.impl, 0.0,
                             f"degraded: flagging failed ({type(exc).__name__}); no flags")
                flags = []
            for result in trace.results:
                result.manipulation_flags = list(flags)
        return trace

    def _live_evidence(self):
        if self._live is None:
            from pipeline.live import LiveEvidence

            self._live = LiveEvidence(to_english=self.cfg.live_translate)
        return self._live

    def _live_stance(self):
        """The NLI model that reads live evidence. With the English route it is
        DeBERTa-v3-large (MNLI/FEVER/ANLI), which tells "capital of India" from
        "capital of Maharashtra" where the multilingual base model called the same
        page Supports (diagnostic, probe set 2); otherwise the served stance model."""
        with self._live_init:
            if self._live_nli is None:
                if self.cfg.live_translate:
                    from stance.nli import NLIStance

                    self._live_nli = NLIStance(model_id=LIVE_NLI_MODEL, max_length=256, offload=True)
                else:
                    return self.stance
            return self._live_nli

    def _get_translator(self):
        with self._live_init:
            if self._translator is None:
                from preprocess.translate import NllbTranslator

                self._translator = NllbTranslator(device=_translator_device())
            return self._translator

    def _live_partner(self):
        """The second NLI model of the validated rule (BART-large-MNLI)."""
        with self._live_init:
            if self._live_partner_nli is None:
                from stance.nli import NLIStance

                self._live_partner_nli = NLIStance(model_id=LIVE_PARTNER_MODEL, max_length=256, offload=True)
            return self._live_partner_nli

    def warm_live(self) -> None:
        """Load the live-verdict models without touching the network, so the first click
        does not pay for loading a translator and two NLI models. No-op unless the live
        verdict is on."""
        if not (self.cfg.live_search and self.cfg.live_verdict and self.cfg.live_translate):
            return
        translator = self._get_translator()
        translator._load()
        translator.translate("warm-up", "en", "hi")                # compile the GPU kernels once
        for nli in (self._live_stance(), self._live_partner()):
            nli.label("Delhi is the capital of India.", ["Delhi is the capital city of India."])

    def _english_claim(self, trace: Trace, claim, forms: list[str]) -> str | None:
        """The claim in English for the live NLI, or None when it is already English
        or cannot be translated (the language-matched path then runs unchanged).
        Romanized input is translated from its native-script form."""
        lang = trace.pre.lang if trace.pre else "en"
        if lang not in ("hi", "pa"):
            return None
        try:
            translator = self._get_translator()
            native = forms[-1] if len(forms) > 1 else claim.text
            english = self._timed(trace, "live", "translate",
                                  lambda: translator.to_english(native, lang))
        except Exception as exc:
            trace.record("live", "translate", 0.0,
                         f"degraded: claim translation failed ({type(exc).__name__}); "
                         "judging in the claim's own language")
            return None
        trace.record("live", "translate", 0.0, f"claim in English: {english}")
        return english

    def _apply_live(self, trace: Trace, claim_idx: int | None) -> None:
        """Re-check each claim with live evidence, on request (post-test Phase 7).

        Free text only: an AVeriTeC claim is ranked within its own evidence pool
        and the evaluation never calls this. Disabled in the pipeline config means
        the request is answered offline and the trace says why -- a refusal the
        user can see, not a silent no-op.
        """
        if claim_idx is not None:
            trace.record("live", "-", 0.0, "live search applies to free text only")
            return
        if not self.cfg.live_search:
            trace.record("live", "-", 0.0, "live search is disabled in this pipeline config")
            return
        for i, result in enumerate(trace.results):
            if result.verdict == "NotAClaim" or result.path == "fast":
                continue                       # nothing to look up / already a fact-check
            try:
                upgraded = self._live_pass(trace, result)
                if upgraded.similar_match is None:        # the similar fact-check survives a live look-up
                    upgraded.similar_match = result.similar_match
                trace.results[i] = upgraded
            except Exception as exc:           # NFR-7: the card keeps its offline answer
                trace.record("live", "-", 0.0,
                             f"degraded: live search failed ({type(exc).__name__}); offline answer kept")

    def _live_pass(self, trace: Trace, result: ClaimResult) -> ClaimResult:
        from pipeline.live import (
            LIVE_RELEVANCE_FLOOR,
            RATED,
            RATED_PROB,
            live_verdict,
            title_grounded,
        )

        claim = result.claim
        forms = self._claim_forms(trace, claim, None)
        lang = trace.pre.lang if trace.pre else "en"
        english = (self._english_claim(trace, claim, forms)
                   if self.cfg.live_verdict and self.cfg.live_translate else None)
        if (self.cfg.live_verdict and self.cfg.live_translate and lang in ("hi", "pa")
                and english is None):
            # The English NLI cannot read a Hindi claim and no title could be grounded
            # in it: keep the offline answer rather than judge blind.
            return result
        if english and english not in forms:
            forms = [*forms, english]
        found = self._timed(trace, "live", "wikipedia+factcheck",
                            lambda: self._live_evidence().gather(forms, lang))
        for note in found.notes:
            trace.record("live", "sources", 0.0, note)

        # A published fact-check of THIS claim answers it, as on the offline fast path.
        if found.match is not None:
            out = self._from_factcheck(trace, claim, found.match)
            out.live_sources = found.sources_used
            return out

        failed = any(n.startswith("degraded") for n in found.notes)
        if not found.passages and failed:
            return result                      # a source was down and nothing came back
        relevant = [p for p in found.passages if p.cosine >= LIVE_RELEVANCE_FLOOR]
        shown = [self._live_passage(i, p) for i, p in enumerate(relevant or found.passages[:3], 1)]
        if not relevant:
            best = max((p.cosine for p in found.passages), default=0.0)
            trace.record("live", "relevance", 0.0,
                         f"no live source is about this claim (best {best:.2f} < "
                         f"{LIVE_RELEVANCE_FLOOR:.2f})")
            out = self._nei_abstain(
                claim, "Wikipedia and published fact-checks were searched, and nothing "
                       "relevant to this claim was found.", passages=shown or None)
            out.live_sources = found.sources_used
            return out

        if not self.cfg.live_verdict:
            # Evidence only: relevant sources, no stance tags, no verdict.
            listed = "; ".join(f"[{p.passage_id[1:]}] {p.title}" for p in shown)
            trace.record("live", "evidence_only", 0.0,
                         "live evidence is listed, not judged (live_verdict is off)")
            return ClaimResult(
                claim=claim, path="evidence", match=None, passages=shown, verdict="NEI",
                confidence=0.0, abstained=True,
                explanation=("TruthLens found these online sources about this claim but does "
                             f"not give a verdict on live evidence: {listed}. Read them."),
                explanation_source="template", explanation_lang="en",
                cited=[p.passage_id for p in shown], live_sources=found.sources_used,
            )

        # A fact-check's stance is its publisher's rating; only Wikipedia is read by NLI,
        # and on the two sentences closest to the claim, not the whole page. With the
        # claim translated, the hypothesis is the English claim and only English pages
        # are judged (a page left in Hindi has no English text to read).
        hypothesis = english or claim.text
        # English route: only a Wikipedia page ABOUT the claim's subject is judged. A
        # fact-check review below the fast-path threshold is a verdict on some OTHER
        # claim (a False-rated Modi story must not refute "Modi is the Prime Minister"),
        # so it is listed, not judged; one that is this claim never gets here (fast path).
        judged = [i for i, p in enumerate(relevant)
                  if not self.cfg.live_translate
                  or (p.source == "wikipedia" and p.lang == "en" and title_grounded(p.title, forms))]
        if self.cfg.live_translate and len(judged) < len(relevant):
            skipped = [p.title for i, p in enumerate(relevant) if i not in judged]
            trace.record("live", "grounding", 0.0,
                         "listed, not judged (not a page about the claim's subject, or a "
                         "fact-check of a different claim): " + "; ".join(skipped))
        nli = [i for i in judged if not relevant[i].rating_stance]
        if self._live_capture is not None:         # evaluation harness only (scripts/live_fever.py)
            self._live_capture.append({
                "hypothesis": hypothesis,
                "judged": [{"title": relevant[i].title, "source": relevant[i].source,
                            "cosine": relevant[i].cosine,
                            "premise": relevant[i].premise or relevant[i].text,
                            "rating_stance": relevant[i].rating_stance} for i in judged],
                "listed": [relevant[i].title for i in range(len(relevant)) if i not in judged]})
        try:
            labels = (self._timed(trace, "stance", self._live_stance().impl,
                                  lambda: self._live_stance().label(
                                      hypothesis, [relevant[i].premise or relevant[i].text for i in nli]))
                      if nli else [])
        except Exception as exc:
            trace.record("stance", self.stance.impl, 0.0,
                         f"degraded: stance failed on live evidence ({type(exc).__name__})")
            return result
        probs: list[dict[str, float]] = [{} for _ in shown]
        for i, label in zip(nli, labels, strict=True):
            probs[i] = label.probs
            shown[i].stance, shown[i].stance_prob = label.stance, label.prob
        for i in judged:
            if relevant[i].rating_stance:
                probs[i] = RATED[relevant[i].rating_stance]
                shown[i].stance, shown[i].stance_prob = relevant[i].rating_stance, RATED_PROB
        weights = [relevant[i].cosine for i in judged]
        verdict, confidence, dist = live_verdict([probs[i] for i in judged], weights)
        agreed = True
        if self.cfg.live_translate and nli:
            # THE VALIDATED RULE (docs/live-fever-protocol-2.md, variant V2): a verdict is shown
            # only if a second NLI model, BART-large-MNLI, reaches the SAME Supported or Refuted
            # verdict from the same passages; confidence is the lower of the two. Anything else
            # is "no verdict". Validated on 350 fresh claims; do not change without a new protocol.
            try:
                partner = self._timed(
                    trace, "stance", "bart_large_mnli",
                    lambda: self._live_partner().label(
                        hypothesis, [relevant[i].premise or relevant[i].text for i in nli]))
            except Exception as exc:
                trace.record("stance", "bart_large_mnli", 0.0,
                             f"degraded: second NLI model failed ({type(exc).__name__}); "
                             "offline answer kept")
                return result
            p_verdict, p_conf, _ = live_verdict([x.probs for x in partner],
                                                [relevant[i].cosine for i in nli])
            agreed = verdict == p_verdict and verdict in ("Supported", "Refuted")
            confidence = min(confidence, p_conf)
            if not agreed:
                trace.record("aggregate", "live_two_model", 0.0,
                             f"the two models did not agree ({verdict} vs {p_verdict}); no verdict")
                verdict = "NEI"
        trace.record("aggregate", "live_weighted", 0.0,
                     "verdict from NLI labels weighted by relevance; the confidence is "
                     "NOT calibrated (no calibration set exists for live evidence)")
        abstained = confidence < self.cfg.tau_abstain or not agreed
        explanation, cited = self.template.explain(verdict, shown, abstained=abstained,
                                                    claim=claim.text)
        return ClaimResult(
            claim=claim, path="evidence", match=None, passages=shown, verdict=verdict,
            confidence=min(max(confidence, 0.0), 1.0), abstained=abstained, verdict_probs=dist,
            explanation=explanation, explanation_source="template", explanation_lang="en",
            cited=cited, live_sources=found.sources_used,
        )

    @staticmethod
    def _live_passage(i: int, p) -> Passage:
        return Passage(passage_id=f"e{i}", doc_id=p.url, text=p.text, url=p.url, title=p.title,
                       retrieval_score=max(0.0, p.cosine), source=p.source)

    def _decide(self, text: str, claim_idx: int | None, force_claim: bool = False) -> Trace:
        trace = Trace(request_id=uuid.uuid4().hex[:12])

        self._timed(trace, "preprocess", self.preprocess.impl,
                    lambda: self.preprocess.run(trace, text))
        assert trace.pre is not None

        if trace.pre.lang == "other":
            trace.record("orchestrator", "-", 0.0, "unsupported language")
            return trace

        trace.checkworthy = self._timed(trace, "claims", self.claims.impl,
                                        lambda: self.claims.check_worthy(trace))
        if not trace.checkworthy and not force_claim:
            trace.results.append(self._not_a_claim(trace))       # FR-6
            return trace

        if not trace.checkworthy:
            # "Check it anyway" (the reader's explicit request, never used in an evaluation): the
            # claim gate called a short fragment ("JEE paper leaked") not a claim, so the whole text
            # is checked as ONE claim instead of being refused.
            trace.checkworthy = True
            trace.claims = [Claim(claim_id="c1", text=trace.pre.normalized.strip(), span=None)]
            trace.record("claims", self.claims.impl, 0.0,
                         "checked anyway at the reader's request: the claim gate had called this not a claim")
        else:
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
        result = self._evidence_path(trace, claim, claim_idx)
        # A fact-check that is probably about something similar, offered to read and never believed:
        # below tau_match there is no verdict from it, but the reader is pointed at it
        # (docs/similar-factcheck-protocol.md). It changes nothing the evidence path decided.
        if self.cfg.tau_similar is not None:
            sim = self._similar_candidate(claim)
            if sim is not None and self.cfg.tau_similar <= sim.score < self.cfg.tau_match:
                result.similar_match = sim
        return result

    def _similar_candidate(self, claim):
        """The matcher's best fact-check as a suggestion; a matcher without one, or one that fails, offers none."""
        offer = getattr(self.matcher, "similar", None)
        if offer is None:
            return None
        try:
            return offer(claim)
        except Exception:
            return None

    def _evidence_path(self, trace: Trace, claim, claim_idx: int | None) -> ClaimResult:
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

        forms = self._claim_forms(trace, claim, claim_idx)
        query = " ".join(forms)
        try:
            scored = self._timed(trace, "retrieval", retriever.impl,
                                 lambda: retriever.topk(query, claim_idx, self.cfg.k))
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
            passages = self._to_passages(query, scored, retriever=retriever)
        except Exception as exc:
            trace.record("retrieval", retriever.impl, 0.0,
                         f"degraded: passage selection failed ({type(exc).__name__}); "
                         "lexical paragraphs")
            passages = self._to_passages(query, scored, lexical=True)

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
        try:
            agg = self._timed(trace, "aggregate", self.aggregator.impl,
                              lambda: self.aggregator.aggregate(probs, dense=dense))
        except FileNotFoundError:
            # NFR-7: no trained aggregator on this machine (CI, a fresh clone).
            # The rule is the always-available floor; the trace says it ran.
            from pipeline.aggregate import RuleAggregator

            trace.record("aggregate", self.aggregator.impl, 0.0,
                         "degraded: no aggregator artifact; rule aggregator")
            agg = RuleAggregator().aggregate(probs)
        abstained = agg.confidence < self.cfg.tau_abstain          # FR-14
        # Free text: if no passage even mentions most of the claim, the verdict
        # is the stance model's claim prior talking, not the evidence -- the
        # Taj Mahal failure. Abstain, keeping the leaning (pipeline/relevance.py).
        if claim_idx is None and self.cfg.free_text_coverage is not None and not abstained:
            from pipeline.relevance import covers_claim

            covered, best = covers_claim(
                forms, [f"{p.title or ''} {p.text}" for p in passages],
                threshold=self.cfg.free_text_coverage)
            if not covered:
                abstained = True
                trace.record("relevance", "coverage", 0.0,
                             f"no passage covers the claim (best {best:.2f} < "
                             f"{self.cfg.free_text_coverage:.2f}): abstained")

        explanation, cited, source, faith = self._explain(
            trace, claim.text, agg.verdict, passages, abstained)
        return ClaimResult(
            claim=claim, path="evidence", match=None, passages=passages,
            verdict=agg.verdict, confidence=agg.confidence, abstained=abstained,
            verdict_probs=getattr(agg, "probs", None),
            explanation=explanation, explanation_source=source,
            # Both explainers write English (FR-17 is cut to English). Reporting
            # the INPUT language for the template made the UI mark English text
            # lang="hi" (a screen reader reads it in a Hindi voice) and hide the
            # "explanation is in English" note -- found rendering real responses.
            explanation_lang="en",
            cited=cited, faithfulness=faith,
        )

    def _claim_forms(self, trace: Trace, claim, claim_idx: int | None) -> list[str]:
        """The claim as typed, plus its native-script form for romanized hi/pa
        free text when `free_text_translit_query` is on."""
        forms = [claim.text]
        pre = trace.pre
        if (claim_idx is None and self.cfg.free_text_translit_query and pre is not None
                and pre.transliterated and pre.lang in ("hi", "pa")):
            transliterate = getattr(self.preprocess, "transliterate", None)
            try:
                native = transliterate(claim.text, pre.lang) if transliterate else None
            except Exception as exc:
                trace.record("preprocess", self.preprocess.impl, 0.0,
                             f"degraded: claim transliteration failed ({type(exc).__name__})")
                native = None
            if native and native != claim.text:
                forms.append(native)
        return forms

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
        # Faithful to SOME passage is not consistent with the VERDICT: a sentence
        # that entails the claim asserts it, which only a Supported verdict may.
        if verdict != "Supported" and hasattr(self.faithfulness, "restates"):
            restated = self.faithfulness.restates(raw, claim_text)
            if restated >= 0.5:
                return template(f"faithfulness: generated explanation restates the claim "
                                f"(entailment {restated:.2f}) under verdict {verdict}; "
                                "template served")
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
