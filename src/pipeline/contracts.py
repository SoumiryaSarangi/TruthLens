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
    manipulation_flags: list[str] = Field(default_factory=list)

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
