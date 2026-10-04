"""Gather live evidence for ONE claim from Wikipedia and Google Fact Check.

Output is raw material, not a verdict: scored passages and, if a published
fact-check is about this very claim, a fast-path match. How they become a verdict
is the orchestrator's job (`Orchestrator._live_pass`).

Relevance is the BGE-M3 cosine between the claim and what a source returned. It
is the one signal that works across languages (the spike: pages that answered a
claim scored 0.5-0.8, irrelevant ones 0.3-0.48), where a word-overlap check
scored a Spanish fact-check 0.00.

Failures never raise: a source that fails is named in `notes`, which go into the
trace, and the claim keeps its offline answer (NFR-7).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from data.verdicts import rating_to_verdict
from pipeline.contracts import FactCheckMatch
from retrieval.live.factcheck import FactCheckHit, GoogleFactCheck
from retrieval.live.http import LiveError
from retrieval.live.wikipedia import WikipediaLive, build_queries

TAU_MATCH = 0.90          # the served fast-path threshold, chosen on dev (Phase 4)
GOOGLE_QUERY_CHARS = 300


@dataclass
class LivePassage:
    text: str
    title: str
    url: str
    source: str              # "wikipedia" | "factcheck_live"
    cosine: float
    lang: str = "en"


@dataclass
class LiveResult:
    passages: list[LivePassage] = field(default_factory=list)
    match: FactCheckMatch | None = None
    notes: list[str] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)


def default_encode(texts: list[str]) -> Sequence[Sequence[float]]:
    from retrieval.encoders import shared_encoder

    return shared_encoder("bge_m3").encode(texts, batch_size=16)


def _cosines(encode, forms: list[str], texts: list[str]) -> list[float]:
    """Best cosine of each text against any form of the claim (typed or native)."""
    if not texts:
        return []
    vectors = encode(forms + texts)
    claim = vectors[:len(forms)]
    return [max(float(sum(a * b for a, b in zip(c, v, strict=True))) for c in claim)
            for v in vectors[len(forms):]]


class LiveEvidence:
    def __init__(self, wikipedia: WikipediaLive | None = None,
                 factcheck: GoogleFactCheck | None = None,
                 encode: Callable[[list[str]], Sequence[Sequence[float]]] = default_encode,
                 tau_match: float = TAU_MATCH, n_wikipedia: int = 5, n_factcheck: int = 3) -> None:
        self.wikipedia = wikipedia or WikipediaLive()
        self.factcheck = factcheck or GoogleFactCheck()
        self.encode = encode
        self.tau_match = tau_match
        self.n_wikipedia = n_wikipedia
        self.n_factcheck = n_factcheck

    # -- the two sources, each isolated so one failing cannot take the other down --
    def _wikipedia(self, forms: list[str], lang: str, result: LiveResult):
        try:
            return self.wikipedia.search(build_queries(forms, lang))
        except LiveError as exc:
            result.notes.append(f"degraded: wikipedia unavailable ({exc})")
            return []

    def _factcheck(self, forms: list[str], result: LiveResult) -> list[FactCheckHit]:
        if not self.factcheck.available:
            result.notes.append("google fact check skipped: no API key configured")
            return []
        hits: dict[str, FactCheckHit] = {}
        try:
            for form in forms:
                for hit in self.factcheck.search(form[:GOOGLE_QUERY_CHARS]):
                    hits.setdefault(hit.url, hit)
        except LiveError as exc:
            result.notes.append(f"degraded: google fact check unavailable ({exc})")
        return list(hits.values())

    def gather(self, forms: list[str], lang: str) -> LiveResult:
        result = LiveResult()
        with ThreadPoolExecutor(max_workers=2) as pool:
            wiki_job = pool.submit(self._wikipedia, forms, lang, result)
            fc_job = pool.submit(self._factcheck, forms, result)
            wiki, hits = wiki_job.result(), fc_job.result()

        try:
            wiki_cos = _cosines(self.encode, forms, [c.text for c in wiki])
            fc_cos = _cosines(self.encode, forms, [h.claim_text or h.title for h in hits])
        except Exception as exc:                       # the encoder failed to load or run
            result.notes.append(f"degraded: relevance scoring failed ({type(exc).__name__})")
            return result

        # A review that IS this claim answers it on the fast path, exactly as offline.
        best_match = None
        for hit, cos in zip(hits, fc_cos, strict=True):
            verdict = rating_to_verdict([hit.rating]) if hit.rating else None
            if cos >= self.tau_match and verdict and (best_match is None or cos > best_match[1]):
                best_match = (hit, cos, verdict)
        if best_match:
            hit, cos, verdict = best_match
            result.match = FactCheckMatch(
                factcheck_id=hit.url, score=cos, verdict=verdict, title=hit.title or hit.claim_text,
                url=hit.url, publisher=hit.publisher or "a fact-checker",
                lang=hit.lang if hit.lang in ("en", "hi", "pa") else "other")
            result.sources_used.append("google_factcheck")

        for hit, cos in sorted(zip(hits, fc_cos, strict=True), key=lambda t: -t[1])[:self.n_factcheck]:
            if result.match and hit.url == result.match.url:
                continue
            # The review's HEADLINE, never its claim text (a rumour stated as fact).
            result.passages.append(LivePassage(hit.title or hit.claim_text, hit.publisher or hit.title,
                                               hit.url, "factcheck_live", cos, hit.lang or "en"))
        for cand, cos in sorted(zip(wiki, wiki_cos, strict=True), key=lambda t: -t[1])[:self.n_wikipedia]:
            result.passages.append(LivePassage(cand.text, cand.title, cand.url, "wikipedia", cos, cand.lang))
        # "Used" means QUERIED successfully, not "returned hits": a search that found
        # nothing is a real answer ("nothing relevant"), a source that was down is not.
        notes = " ".join(result.notes)
        if "wikipedia unavailable" not in notes and "wikipedia" not in result.sources_used:
            result.sources_used.append("wikipedia")
        if (self.factcheck.available and "google fact check unavailable" not in notes
                and "google_factcheck" not in result.sources_used):
            result.sources_used.append("google_factcheck")
        result.passages.sort(key=lambda p: -p.cosine)
        return result


# -- from live passages to a verdict ----------------------------------------------
#
# Fixed BEFORE the probe set was run, not tuned on it.
#
# Why not the learned aggregator: the spike gave it the right Wikipedia evidence
# for four TRUE claims (Delhi, Modi, Harmandir Sahib, Lahore) and it still said
# Refuted, 0.61-0.89 -- its "a forwarded claim is probably false" prior outweighs
# what the passages say, and it was never trained on live evidence. The NLI labels
# were right on all four. So the live path reads the NLI per-passage labels
# directly, weighted by relevance.

LIVE_RELEVANCE_FLOOR = 0.5      # a page below this BGE-M3 cosine is not about the claim
CONFLICT_MIN = 0.25             # both sides need this much weighted mass ...
CONFLICT_RATIO = 0.6            # ... and the weaker must be this close to the stronger


def live_verdict(probs: Sequence[dict[str, float]],
                 weights: Sequence[float]) -> tuple[str, float, dict[str, float]]:
    """(verdict, confidence, distribution) from per-passage NLI labels.

    Relevance-weighted MEAN, not max: one weakly relevant page that refutes (the
    "Black Taj Mahal" legend, cosine 0.65) must not outvote three strong pages
    that support. The confidence is that mean -- NOT calibrated (no calibration
    set exists for live evidence) and the caller says so in the trace.
    """
    total = sum(max(w, 0.0) for w in weights)
    if not probs or total <= 0:
        return "NEI", 0.0, {"Supported": 0.0, "Refuted": 0.0, "Conflicting": 0.0, "NEI": 1.0}

    def mean(label: str) -> float:
        return sum(max(w, 0.0) * p.get(label, 0.0) for p, w in zip(probs, weights, strict=True)) / total

    support, refute, neutral = mean("Supports"), mean("Refutes"), mean("Neutral")
    dist = {"Supported": support, "Refuted": refute, "Conflicting": 0.0, "NEI": neutral}
    strong, weak = max(support, refute), min(support, refute)
    if weak >= CONFLICT_MIN and weak / strong >= CONFLICT_RATIO:
        dist["Conflicting"] = min(1.0, support + refute)
        return "Conflicting", dist["Conflicting"], dist
    if strong > neutral:
        return ("Supported", support, dist) if support >= refute else ("Refuted", refute, dist)
    return "NEI", neutral, dist
