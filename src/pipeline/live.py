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

import re
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from data.verdicts import rating_to_verdict
from pipeline.contracts import FactCheckMatch
from retrieval.live.factcheck import FactCheckHit, GoogleFactCheck
from retrieval.live.http import LiveError
from retrieval.live.wikipedia import WikipediaLive, build_queries, build_queries_v2

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
    # What the stance model reads, when that is not the whole passage: the two
    # sentences closest to the claim. A lead plus a snippet is a blob; probe run 1
    # had NLI call whole pages 'Supports' because they were about the same topic.
    premise: str = ""
    # For a fact-check review: the stance its PUBLISHER'S rating gives. A fact-check
    # is a human verdict on a claim, so it is read from the rating, never from NLI
    # over a headline that restates the rumour.
    rating_stance: str | None = None


@dataclass
class LiveResult:
    passages: list[LivePassage] = field(default_factory=list)
    match: FactCheckMatch | None = None
    notes: list[str] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)


_SENTENCE = re.compile(r"(?<=[.!?\u0964])\s+|\s\u2026\s")
RATING_STANCE = {"Refuted": "Refutes", "Supported": "Supports"}
RATED_PROB = 0.9        # how sure a publisher's rating makes the stance (not model output)
RATED = {s: {"Supports": 0.0, "Refutes": 0.0, "Neutral": 0.0} | {s: RATED_PROB, "Neutral": 1 - RATED_PROB}
         for s in ("Supports", "Refutes")} | {"Neutral": {"Supports": 0.0, "Refutes": 0.0, "Neutral": 1.0}}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if len(s.strip()) >= 20]


def rating_stance(rating: str) -> str:
    """Supports / Refutes / Neutral from a publisher's rating; unmappable is Neutral."""
    return RATING_STANCE.get(rating_to_verdict([rating]) or "", "Neutral") if rating else "Neutral"


# -- entity grounding ---------------------------------------------------------------
#
# Probe set 3's two live errors were relevance errors: the NLI read the WRONG page
# correctly ("Daman Ganga" and "Varahi" are rivers that do reach the Arabian Sea; a
# market page loosely matched a tea stall). A page may be JUDGED only if its title
# is about the claim's subject: every content word of the title must match a word of
# the claim. Words are compared by consonant skeleton, so spelling variants agree
# (Bangalore/Bengaluru, Ganga/Ganges) while "Daman Ganga River" does not match
# "Ganga falls into the Arabian Sea" (daman has no counterpart).
# Fixed before probe set 4 was drafted; tuned on nothing.

TITLE_GENERIC = frozenset({
    "a", "an", "the", "of", "in", "and", "on", "at", "to", "for", "by", "or",
    "list", "river", "city", "district", "state", "town", "article", "disambiguation",
})
_WORD = re.compile(r"[a-z0-9]+")
_VOWELS = re.compile(r"[aeiouy]")
_PARENS = re.compile(r"\([^)]*\)")
SKELETON_MIN = 3


def skeleton(word: str) -> str:
    """A word with its vowels removed and doubled letters collapsed ('Bengaluru' -> 'bnglr')."""
    consonants = _VOWELS.sub("", word.lower())
    return re.sub(r"(.)\1+", r"\1", consonants) or word.lower()


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    sa, sb = skeleton(a), skeleton(b)
    short, long_ = sorted((sa, sb), key=len)
    return len(short) >= SKELETON_MIN and long_.startswith(short)


def title_grounded(title: str, claim_forms: Sequence[str]) -> bool:
    """True if every content word of `title` has a counterpart in some Latin-script
    form of the claim. A title with no content words (a bare 'List of ...') is not grounded."""
    words = [w for w in _WORD.findall(_PARENS.sub(" ", title).lower()) if w not in TITLE_GENERIC]
    claim = {w for form in claim_forms if form.isascii() for w in _WORD.findall(form.lower())}
    return bool(words) and all(any(_same_word(w, c) for c in claim) for w in words)


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
                 tau_match: float = TAU_MATCH, n_wikipedia: int = 5, n_factcheck: int = 3,
                 to_english: bool = False, retrieval_v2: bool = False) -> None:
        self.wikipedia = wikipedia or WikipediaLive()
        self.factcheck = factcheck or GoogleFactCheck()
        self.encode = encode
        self.tau_match = tau_match
        self.n_wikipedia = n_wikipedia
        self.n_factcheck = n_factcheck
        self.to_english = to_english      # read English Wikipedia (the translated-claim route)
        self.retrieval_v2 = retrieval_v2  # entity and acronym queries, deeper candidates (docs/live-retrieval-v2-protocol.md)

    # -- the two sources, each isolated so one failing cannot take the other down --
    def _wikipedia(self, forms: list[str], lang: str, result: LiveResult):
        try:
            queries = build_queries_v2(forms, lang) if self.retrieval_v2 else build_queries(forms, lang)
            return self.wikipedia.search(queries, to_english=self.to_english)
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

    def _premise(self, forms: list[str], text: str, n: int = 2) -> str:
        """The `n` sentences of `text` closest to the claim, in their original order."""
        sentences = split_sentences(text)
        if len(sentences) <= n:
            return text
        try:
            cos = _cosines(self.encode, forms, sentences)
        except Exception:
            return text
        keep = sorted(sorted(range(len(sentences)), key=lambda i: -cos[i])[:n])
        return " ".join(sentences[i] for i in keep)

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
            # The publisher's own rating travels with the headline: a human
            # fact-checker's verdict, shown as theirs, never converted by a model.
            headline = hit.title or hit.claim_text
            text = f"{headline} — {hit.publisher or 'fact-checker'} rating: {hit.rating}" if hit.rating else headline
            result.passages.append(LivePassage(text, hit.publisher or hit.title, hit.url,
                                               "factcheck_live", cos, hit.lang or "en",
                                               rating_stance=rating_stance(hit.rating)))
        for cand, cos in sorted(zip(wiki, wiki_cos, strict=True), key=lambda t: -t[1])[:self.n_wikipedia]:
            result.passages.append(LivePassage(
                cand.text, cand.title, cand.url, "wikipedia", cos, cand.lang,
                premise=self._premise(forms, cand.text)))
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
REFUTER = 0.5                   # a passage this sure it refutes blocks "Supported"


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
        if support >= refute:
            # A false 'Supported' is the worst error a misinformation tool can make
            # (probe run 1: three of them). So Supported cannot stand over a relevant
            # passage that refutes: it is Conflicting, which the user reads as 'look'.
            if any(p.get("Refutes", 0.0) >= REFUTER for p in probs):
                dist["Conflicting"] = min(1.0, support + refute)
                return "Conflicting", dist["Conflicting"], dist
            return "Supported", support, dist
        return "Refuted", refute, dist
    return "NEI", neutral, dist
