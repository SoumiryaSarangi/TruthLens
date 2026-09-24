"""Claims stage. Phase 1 is a passthrough; the real filter is Phase 3.

Worth testing anyway, because its behaviour has a direct and easily-forgotten
consequence for the metrics: it never emits NotAClaim, so that class has zero
predictions and macro-F1 is capped.
"""

from __future__ import annotations

import pytest

from claims.passthrough import PassthroughClaims
from pipeline.contracts import MAX_CLAIMS, Preprocessed, Trace


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


# -----------------------------------------------------------------------------
# The rules implementation (FR-6, FR-7) -- no weights, so this runs in CI
# -----------------------------------------------------------------------------

from claims.heuristic import HeuristicClaims, is_check_worthy, split_sentences  # noqa: E402


def test_empty_and_tiny_messages_are_not_check_worthy():
    assert is_check_worthy("") is False
    assert is_check_worthy("   ") is False
    assert is_check_worthy("Good morning") is False


def test_a_scheme_claim_is_check_worthy():
    assert is_check_worthy(
        "Sarkar ne announce kiya hai ki har student ko 6000 rupaye milegi"
    ) is True


def test_the_rules_cannot_catch_a_wordy_blessing_and_that_is_the_finding():
    """Pins the measured limitation rather than a target.

    Rules catch short or empty messages. They do not catch "wordy but asserts
    nothing", which is exactly what a blessing is -- it has plenty of content
    words and nothing a fact-checker could look up. Measured on the hand-typed
    set, this implementation catches 0 of 15 no-claim messages and ties
    majority_class exactly.

    If a future change makes this pass, that is a real improvement and the
    numbers in docs/results.md need updating -- which is why it fails loudly
    here instead of being a comment nobody reads.
    """
    blessing = "Sat Sri Akal ji Rabb sabnu khush rakhe. Ehna sandesh dostan nu bhejo"
    assert is_check_worthy(blessing) is True, (
        "the rules now reject a wordy blessing. That is an improvement -- "
        "re-run configs/p3_cw_handtyped_heuristic.yaml and update the reported "
        "figures rather than this assertion."
    )


def test_danda_ends_a_sentence():
    """Splitting on `.` alone would treat a whole Hindi forward as one sentence."""
    assert len(split_sentences("\u092f\u0947 \u0938\u091a \u0939\u0948\u0964 "
                               "\u0935\u094b \u0928\u0939\u0940\u0902 \u0939\u0948\u0964")) == 2


def test_heuristic_extract_respects_the_cap(monkeypatch):
    stage = HeuristicClaims()
    trace = trace_with("Sarkar ne kaha ek. Sarkar ne kaha do. Sarkar ne kaha teen. "
                       "Sarkar ne kaha chaar aur paanch bhi.")
    stage.extract(trace)
    assert len(trace.claims) <= MAX_CLAIMS
    assert trace.unchecked_claims          # the overflow is listed, not dropped


# -----------------------------------------------------------------------------
# The orchestrator enforces FR-7's cap, whatever the extractor does
# -----------------------------------------------------------------------------


def test_orchestrator_caps_claims_even_if_the_extractor_does_not():
    """FR-7's "at most 3" is a promise the API makes, not an extractor's habit.

    Each extra claim costs a full retrieval and NLI pass, so an over-producing
    extractor is expensive as well as wrong. This passes one that ignores the
    cap entirely and checks the orchestrator still keeps the promise.
    """
    from pipeline.contracts import Claim
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    class Greedy:
        name, impl = "claims", "greedy-test-double"

        def check_worthy(self, trace):
            return True

        def extract(self, trace):
            trace.claims = [Claim(claim_id=f"c{i}", text=f"claim {i}")
                            for i in range(1, 8)]
            trace.unchecked_claims = []
            return trace

    orch = Orchestrator(PipelineConfig())
    orch.claims = Greedy()
    trace = orch.verify("Sarkar ne kaha ki yeh sach hai")

    assert len(trace.claims) == MAX_CLAIMS
    assert len(trace.unchecked_claims) == 4
    assert any(e.note and "capped" in e.note for e in trace.events)
