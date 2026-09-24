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


# -----------------------------------------------------------------------------
# The fine-tuned span model. Only the parts that need no GPU -- which is all the
# logic that turns a tag sequence into claims, and every refusal path.
# -----------------------------------------------------------------------------

from claims.span_xlmr import AdapterUnavailable, SpanXLMRClaims  # noqa: E402
from data.labels import SPAN_BIO  # noqa: E402

BEGIN, INSIDE, OUT = SPAN_BIO      # ("B-CLAIM", "I-CLAIM", "O")


@pytest.mark.parametrize("tags, expected", [
    ([], []),
    ([OUT, OUT, OUT], []),
    ([BEGIN], [(0, 0)]),
    ([BEGIN, INSIDE, INSIDE], [(0, 2)]),
    ([OUT, BEGIN, INSIDE, OUT], [(1, 2)]),
    ([BEGIN, INSIDE, OUT, BEGIN, INSIDE], [(0, 1), (3, 4)]),
    # A fresh BEGIN ends the previous run: two claims that touch stay two claims,
    # which is the whole reason the tag set has a BEGIN at all.
    ([BEGIN, INSIDE, BEGIN, INSIDE], [(0, 1), (2, 3)]),
    # A run that starts with INSIDE is malformed -- the model can emit it -- and is
    # read as a span rather than dropped. Dropping it would silently lower
    # recall on exactly the rows the model was least sure about.
    ([INSIDE, INSIDE, OUT], [(0, 1)]),
    ([OUT, OUT, BEGIN, INSIDE], [(2, 3)]),
])
def test_spans_from_tags(tags, expected):
    """Inclusive index pairs, matching X-CLAIM's own convention (see
    tests/test_loader_xclaim.py). Pure and static, so it is tested directly."""
    assert SpanXLMRClaims.spans_from_tags([""] * len(tags), tags) == expected


def test_a_missing_adapter_refuses_and_says_how_to_make_one(tmp_path):
    """Degrade, record it, never invent -- SYSTEM_DESIGN 11.

    The failure that matters here is the quiet one: an untrained adapter that
    loads the base model anyway would produce a complete, plausible predictions
    file measuring an untrained classifier head.
    """
    stage = SpanXLMRClaims(adapter=tmp_path / "not-trained")
    assert stage.available is False
    with pytest.raises(AdapterUnavailable) as excinfo:
        stage._load()
    assert "train_span.py" in str(excinfo.value)


def test_availability_is_decided_by_the_adapter_config(tmp_path):
    (tmp_path / "adapter_config.json").write_text("{}", encoding="utf-8")
    stage = SpanXLMRClaims(adapter=tmp_path, cw_adapter=tmp_path / "none")
    assert stage.available is True
    assert stage.cw_available is False


def test_blank_text_is_rejected_before_any_model_loads(tmp_path):
    """No adapter exists here, so anything that touched one would raise."""
    stage = SpanXLMRClaims(adapter=tmp_path / "none", cw_adapter=tmp_path / "none")
    assert stage.check_worthy(trace_with("   ")) is False


def test_extract_uses_the_tagger_and_honours_the_cap(monkeypatch, tmp_path):
    """Four spans in, three claims out, the fourth listed rather than dropped."""
    stage = SpanXLMRClaims(adapter=tmp_path / "none")
    text = "aaaa bbbb cccc and dddd eeee and ffff gggg and hh"
    tags = {"aaaa": BEGIN, "bbbb": INSIDE, "cccc": INSIDE, "dddd": BEGIN, "eeee": INSIDE,
            "ffff": BEGIN, "gggg": INSIDE, "hh": BEGIN}
    monkeypatch.setattr(stage, "tag",
                        lambda tokens: [tags.get(t, OUT) for t in tokens])

    trace = stage.extract(trace_with(text))
    assert [c.text for c in trace.claims] == ["aaaa bbbb cccc", "dddd eeee", "ffff gggg"]
    assert trace.unchecked_claims == ["hh"]
    assert len(trace.claims) == MAX_CLAIMS


def test_extract_falls_back_to_the_whole_post_when_nothing_is_tagged(monkeypatch,
                                                                     tmp_path):
    """Correct for PRODUCING claims and wrong for SCORING a tagger, which is why
    `pipeline.batch._span_tags` bypasses this path. Pinned so the two stay
    distinguishable: measured on the joint arm, the round trip moved token F1
    from 0.7463 to 0.7038."""
    stage = SpanXLMRClaims(adapter=tmp_path / "none")
    monkeypatch.setattr(stage, "tag", lambda tokens: [OUT] * len(tokens))
    trace = stage.extract(trace_with("Sarkar ne kaha yeh sach hai"))
    assert [c.text for c in trace.claims] == ["Sarkar ne kaha yeh sach hai"]


def test_claim_spans_are_character_offsets_into_the_text(monkeypatch, tmp_path):
    """The `Claim.span` contract is character offsets, not token indices."""
    stage = SpanXLMRClaims(adapter=tmp_path / "none")
    text = "Good morning. Sarkar ne kaha."
    monkeypatch.setattr(stage, "tag", lambda tokens: [OUT, OUT, BEGIN, INSIDE, INSIDE])
    trace = stage.extract(trace_with(text))
    start, end = trace.claims[0].span
    assert text[start:end] == trace.claims[0].text


# -----------------------------------------------------------------------------
# The zero-shot NLI arm (FR-6). The decision rule is pure, so it runs in CI.
# -----------------------------------------------------------------------------

from claims.nli_zeroshot import ENTAILMENT, NLIZeroShotClaims, decide  # noqa: E402


def test_the_rule_thresholds_entailment_rather_than_taking_an_argmax():
    """A threshold can go below 0.5; an argmax cannot.

    Neutral is the argmax for most short texts, so an argmax rule would answer
    "not check-worthy" to nearly everything. Thresholding is what makes the
    operating point adjustable at all -- which is the only knob this arm has,
    since nothing about it is trained.
    """
    neutral_wins = {ENTAILMENT: 0.40, "Refutes": 0.05, "Neutral": 0.55}
    assert max(neutral_wins, key=neutral_wins.get) == "Neutral"
    assert decide(neutral_wins, threshold=0.5) is False
    assert decide(neutral_wins, threshold=0.3) is True


@pytest.mark.parametrize("p, threshold, expected", [
    (0.9, 0.5, True),
    (0.5, 0.5, True),          # the boundary is inclusive
    (0.49, 0.5, False),
    (0.6, 0.7, False),
    (0.0, 0.5, False),
])
def test_the_threshold_is_the_only_knob(p, threshold, expected):
    assert decide({ENTAILMENT: p, "Neutral": 1 - p}, threshold) is expected


def test_a_missing_entailment_key_is_not_check_worthy():
    """A model whose labels were ordered differently must not silently pass
    everything. `NLIStance` raises on an unexpected label set; this is the
    second line of defence."""
    assert decide({"Neutral": 0.9}) is False


def test_blank_text_needs_no_model():
    """Constructing the stage must not import torch, and a blank message must
    not load a 0.6 GB model to be told it says nothing."""
    stage = NLIZeroShotClaims()
    assert stage.check_worthy(trace_with("  ")) is False
    assert stage._nli is None


def test_extraction_is_delegated_to_the_rules():
    """This arm answers FR-6 only. Mixing in a different extractor would make
    the comparison against the trained classifier two changes wide."""
    stage = NLIZeroShotClaims()
    trace = stage.extract(trace_with("Sarkar ne kaha ki har student ko 6000 milenge."))
    assert [c.text for c in trace.claims] == [
        "Sarkar ne kaha ki har student ko 6000 milenge."]
