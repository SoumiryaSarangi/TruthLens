"""The served claims stage: rules decide IF there is a claim, the span model WHICH.

Two halves, each the arm measured best at its own job:

- **check-worthiness (FR-6)** stays the heuristic. The span model cannot answer
  "no claim" (X-CLAIM has no negatives) and the trained classifier fails on real
  forwards; Phase 3 and the served-config notes have the numbers.
- **extraction (FR-7)** reads the joint XLM-R span model. The heuristic made
  every non-greeting sentence of 4+ words a claim, and scored token F1 0.7095
  on X-CLAIM dev (p7_span_heuristic) -- barely above calling the whole post the
  claim (0.6851) -- against the joint model's 0.7463. On real forwards that
  meant verifying "Dosto dhyan se padho!!" and refuting it at 0.83.

Extraction is still sentence-level: the heuristic proposes sentences, the span
model (run once over the whole post, for context) says what share of each
sentence's tokens is claim, and sentences are kept by that share. A whole
sentence is a cleaner retrieval query than a token span cut mid-phrase.

**A forward with at most one candidate sentence never reaches the model** and
gets exactly the heuristic's answer -- so a one-sentence AVeriTeC claim is
extracted as before, and the verdict numbers can only move on multi-sentence
inputs.
"""

from __future__ import annotations

import os
import re

from claims.heuristic import HeuristicClaims, is_check_worthy, split_sentences
from pipeline.contracts import MAX_CLAIMS, Claim, Trace

OUTSIDE = "O"
KEEP_SHARE = 0.5      # a sentence is a claim if at least half its tokens are tagged


def sentence_shares(text: str, sentences: list[str], tags: list[str]) -> list[float]:
    """Share of each sentence's whitespace tokens that the span model tagged."""
    starts = [m.start() for m in re.finditer(r"\S+", text)]
    assert len(starts) == len(tags), "tags must align with text.split()"
    shares, cursor = [], 0
    for sentence in sentences:
        begin = text.find(sentence, cursor)
        if begin < 0:
            shares.append(0.0)
            continue
        end = begin + len(sentence)
        cursor = end
        inside = [i for i, s in enumerate(starts) if begin <= s < end]
        tagged = sum(1 for i in inside if tags[i] != OUTSIDE)
        shares.append(tagged / len(inside) if inside else 0.0)
    return shares


class HeuristicSpanClaims:
    """`claims: heuristic_span` -- see the module docstring."""

    name = "claims"
    impl = "heuristic_span"

    def __init__(self, adapter: str | os.PathLike[str] | None = None, tagger=None, **kwargs):
        self._rules = HeuristicClaims()
        self._tagger = tagger
        self._adapter = adapter
        self._kwargs = kwargs

    @property
    def tagger(self):
        if self._tagger is None:
            from claims.span_xlmr import SpanXLMRClaims

            self._tagger = SpanXLMRClaims(adapter=self._adapter, **self._kwargs)
        return self._tagger

    @property
    def loaded(self) -> bool:
        return self._tagger is not None

    def check_worthy(self, trace: Trace) -> bool:
        return self._rules.check_worthy(trace)

    def extract(self, trace: Trace) -> Trace:
        assert trace.pre is not None
        text = trace.pre.normalized
        candidates = [s for s in split_sentences(text) if is_check_worthy(s)]
        if len(candidates) <= 1:
            return self._rules.extract(trace)            # identical to the heuristic

        tags = self.tagger.tag(text.split())
        shares = sentence_shares(text, candidates, tags)
        kept = [(share, s) for share, s in zip(shares, candidates, strict=True)
                if share >= KEEP_SHARE]
        if not kept:
            # The model tagged no sentence as mostly claim: verify its best guess,
            # or the longest sentence if it tagged nothing at all -- one claim,
            # never every sentence.
            best = max(zip(shares, candidates, strict=True), key=lambda p: (p[0], len(p[1])))
            kept = [best]
        ranked = [s for _, s in sorted(kept, key=lambda p: (-p[0], -len(p[1])))]

        trace.claims = [
            Claim(claim_id=f"c{i}", text=s, span=_locate(text, s))
            for i, s in enumerate(ranked[:MAX_CLAIMS], start=1)
        ]
        trace.unchecked_claims = ranked[MAX_CLAIMS:]
        return trace


def _locate(haystack: str, needle: str) -> tuple[int, int] | None:
    start = haystack.find(needle)
    return (start, start + len(needle)) if start >= 0 else None
