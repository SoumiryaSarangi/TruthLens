"""Claims stage. Phase 1 is a passthrough; the real filter is Phase 3.

Worth testing anyway, because its behaviour has a direct and easily-forgotten
consequence for the metrics: it never emits NotAClaim, so that class has zero
predictions and macro-F1 is capped.
"""

from __future__ import annotations

import pytest

from claims.passthrough import MAX_CLAIMS, PassthroughClaims
from pipeline.contracts import Preprocessed, Trace


def trace_with(text: str) -> Trace:
    t = Trace(request_id="t")
    t.pre = Preprocessed(original=text, normalized=text, lang="en", script="latn",
                         script_purity=1.0)
    return t


@pytest.fixture
def stage():
    return PassthroughClaims()


def test_non_empty_text_is_check_worthy(stage):
    assert stage.check_worthy(trace_with("The minister resigned.")) is True


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_blank_text_is_not_check_worthy(stage, text):
    """FR-6: a non-check-worthy forward short-circuits, with no retrieval."""
    assert stage.check_worthy(trace_with(text)) is False


def test_the_whole_input_becomes_one_claim(stage):
    t = stage.extract(trace_with("The minister resigned on Tuesday."))
    assert len(t.claims) == 1
    assert t.claims[0].claim_id == "c1"
    assert t.claims[0].text == "The minister resigned on Tuesday."


def test_nothing_is_reported_as_unchecked_in_phase_1(stage):
    assert stage.extract(trace_with("A claim.")).unchecked_claims == []


def test_the_max_claims_cap_is_declared(stage):
    """FR-7 caps verification at 3 claims. Phase 1 only ever produces one, but
    the constant is the contract Phase 3's extractor must honour."""
    assert MAX_CLAIMS == 3
