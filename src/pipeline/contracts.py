"""The data contract every stage reads and writes. SYSTEM_DESIGN.md §4.

Label strings are **imported** from `src/data/labels.py`, never retyped. That
module is the single label registry, and a second copy of "Refuted" in this
file is how a label set starts to rot.

Nothing here imports torch, transformers or any model library. CI runs on the
core lock with no torch installed, and these contracts -- and their tests --
must run there.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from data.labels import STANCE_3CLASS, VERDICT_5CLASS
from data.script_id import SCRIPTS

# `Lang` adds "other", which is RUNTIME ONLY: it exists so an unsupported
# language request has somewhere to go. `src/data/splits.py` allows only
# en/hi/pa and rejects anything else, and no split row is ever "other".
Lang = Literal["en", "hi", "pa", "other"]

# Exactly the three values `script_id.detect_script` returns. No "mixed" --
# code-mixing is carried as the continuous `Preprocessed.script_purity`.
Script = Literal["deva", "guru", "latn"]

Stance = Literal["Supports", "Refutes", "Neutral"]
Verdict = Literal["Supported", "Refuted", "Conflicting", "NEI", "NotAClaim"]

Path_ = Literal["fast", "evidence", "none"]
ExplanationSource = Literal["generated", "template"]

# These asserts are the actual enforcement. If someone edits labels.py without
# editing here, imports fail immediately rather than at eval time.
assert set(Stance.__args__) == set(STANCE_3CLASS), "Stance drifted from STANCE_3CLASS"
assert set(Verdict.__args__) == set(VERDICT_5CLASS), "Verdict drifted from VERDICT_5CLASS"
assert set(Script.__args__) == set(SCRIPTS), "Script drifted from script_id.SCRIPTS"


class Preprocessed(BaseModel):
    original: str
    normalized: str
    lang: Lang
    script: Script
    script_purity: float = Field(ge=0.0, le=1.0)
    transliterated: str | None = None


# FR-7: at most this many claims per forward are verified; the rest are listed
# as not checked. Defined once, here, because it is part of the Claim contract
# and not a property of any one extractor -- it had drifted into three separate
# copies across src/claims/ before the orchestrator started enforcing it.
MAX_CLAIMS = 3


class Claim(BaseModel):
    claim_id: str
    text: str
    span: tuple[int, int] | None = None


class FactCheckMatch(BaseModel):
    factcheck_id: str
    score: float
    verdict: Verdict
    title: str
    url: str
    publisher: str
    lang: Lang
    # The fact-checked CLAIM as the fact-checker or the index states it (not the review headline). Only the polarity guard
    # reads it (docs/polarity-guard-v2-protocol.md); None when the source did not give one.
    claim_text: str | None = None


class SimilarMatch(BaseModel):
    """The best published fact-check offered as "a fact-checker looked at something similar".

    Like FactCheckMatch but the rating may be absent: a fact-check whose rating cannot be mapped to
    a verdict is still worth reading, and the suggestion makes no verdict from it.
    """

    factcheck_id: str
    score: float
    verdict: Verdict | None = None
    title: str
    url: str
    publisher: str
    lang: Lang


class Passage(BaseModel):
    passage_id: str
    doc_id: str
    text: str
    url: str | None = None
    title: str | None = None
    retrieval_score: float
    stance: Stance | None = None
    stance_prob: float | None = None
    highlight: tuple[int, int] | None = None
    # Where a passage came from when it is not from the offline corpus:
    # "wikipedia" or "factcheck_live" (post-test Phase 7). None = the offline
    # corpus or an AVeriTeC pool. The UI badges live sources and attributes them.
    source: str | None = None
    # The text the NLI models actually read for a live passage (the two sentences nearest the claim), kept so
    # the optional word view can re-read exactly it. None for offline passages.
    premise: str | None = None


class ClaimResult(BaseModel):
    claim: Claim
    path: Path_
    match: FactCheckMatch | None = None
    passages: list[Passage] = Field(default_factory=list)
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool
    explanation: str
    explanation_source: ExplanationSource
    explanation_lang: Lang
    cited: list[str] = Field(default_factory=list)
    faithfulness: float | None = None
    # The aggregator's full verdict distribution, when it has one (the learned
    # aggregator does; the rule does not). What calibration is measured on.
    verdict_probs: dict[str, float] | None = None
    manipulation_flags: list[str] = Field(default_factory=list)
    # Live sources consulted for this result, when the user asked for them.
    live_sources: list[str] = Field(default_factory=list)
    # The best published fact-check when it scored below tau_match (so no fast-path verdict) but at
    # or above tau_similar: a SUGGESTION to read, never a verdict. docs/similar-factcheck-protocol.md
    similar_match: SimilarMatch | None = None
    # Why the claim gate refused this text ("greeting", "too_short", "no_content"); only on NotAClaim.
    gate_reason: Literal["greeting", "too_short", "no_content"] | None = None
    # The English claim a live verdict was judged on (the translation, for Hindi, Punjabi and Roman input).
    claim_en: str | None = None
    # True when a live look-up found sources that point opposite ways (both models read it as Conflicting), so the
    # card can say "the sources disagree" and not the generic "nothing checks this". Wording only; no verdict moves.
    sources_disagree: bool = False

    @field_validator("explanation_source")
    @classmethod
    def _abstained_is_never_generated(cls, v: str, info) -> str:
        """SYSTEM_DESIGN.md §2 and §11: an abstained verdict never gets prose.

        Enforced here rather than trusted to each generation implementation --
        the whole point of abstaining is that the system does not stand behind
        the answer, and fluent generated text arguing for it undercuts that.
        """
        if info.data.get("abstained") and v == "generated":
            raise ValueError(
                "an abstained result must use the template explanation, not generated "
                "prose (SYSTEM_DESIGN.md §11)"
            )
        return v


class Event(BaseModel):
    stage: str
    impl: str
    ms: float
    note: str | None = None


class Trace(BaseModel):
    request_id: str
    pre: Preprocessed | None = None
    checkworthy: bool | None = None
    claims: list[Claim] = Field(default_factory=list)
    results: list[ClaimResult] = Field(default_factory=list)
    unchecked_claims: list[str] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)

    def record(self, stage: str, impl: str, ms: float, note: str | None = None) -> None:
        self.events.append(Event(stage=stage, impl=impl, ms=ms, note=note))
