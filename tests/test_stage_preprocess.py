"""Preprocess stage. Covers FR-2 and FR-4.

FR-2 was implemented in Phase 1 and had no test until now: the model-facing
artefact stripping is easy to break in a way that leaves the pipeline working
and the inputs subtly wrong, which is exactly the class of bug that survives to
the report.
"""

from __future__ import annotations

import pytest

from pipeline.contracts import Trace
from preprocess.passthrough import PassthroughPreprocess


@pytest.fixture
def stage():
    return PassthroughPreprocess()


def run(stage, text: str):
    return stage.run(Trace(request_id="t"), text).pre


# -----------------------------------------------------------------------------
# FR-2: strip forward artefacts for processing, KEEP the original
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", [
    "Forwarded many times: ",
    "Forwarded: ",
    "Forwarded message - ",
    "Sent as received: ",
    "FORWARDED MANY TIMES ",
])
def test_forward_artefacts_are_stripped(stage, prefix):
    pre = run(stage, prefix + "The minister resigned on Tuesday.")
    assert pre.normalized == "The minister resigned on Tuesday."


def test_stacked_forward_headers_are_all_stripped(stage):
    """Real forwards accumulate headers as they are passed along."""
    pre = run(stage, "Forwarded many times: Forwarded: The minister resigned.")
    assert pre.normalized == "The minister resigned."


def test_the_original_text_is_preserved_verbatim(stage):
    """FR-2 explicitly requires the raw text to survive into the response."""
    raw = "Forwarded many times:   The   minister resigned.  "
    pre = run(stage, raw)
    assert pre.original == raw
    assert pre.normalized != raw


def test_whitespace_is_collapsed_not_removed(stage):
    assert run(stage, "The   minister\n\nresigned.").normalized == "The minister resigned."


def test_text_without_artefacts_is_left_alone(stage):
    claim = "Hospitals in Kerala reported 300 dengue cases."
    assert run(stage, claim).normalized == claim


def test_a_claim_merely_mentioning_forwarding_is_not_truncated(stage):
    """The rule anchors at the start; it must not eat content mid-sentence."""
    claim = "The minister said the message was forwarded many times before."
    assert run(stage, claim).normalized == claim


# -----------------------------------------------------------------------------
# FR-4: script per row, never inferred from a language label
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("text,script", [
    ("The minister resigned on Tuesday.", "latn"),
    ("सरकार सभी किसानों को मुफ्त बिजली दे रही है।", "deva"),
    ("ਸਰਕਾਰ ਸਾਰੇ ਕਿਸਾਨਾਂ ਨੂੰ ਮੁਫਤ ਬਿਜਲੀ ਦੇ ਰਹੀ ਹੈ।", "guru"),
])
def test_script_is_detected_from_the_text(stage, text, script):
    assert run(stage, text).script == script


def test_script_purity_is_reported(stage):
    """Code-mixing is a float, not a fourth script value (SYSTEM_DESIGN §4)."""
    pure = run(stage, "The minister resigned on Tuesday.")
    mixed = run(stage, "Sarkar ne kaha कि यह सच है and people believed it")
    assert pure.script_purity == pytest.approx(1.0)
    assert mixed.script_purity < 1.0


def test_phase_1_language_guess_is_script_derived(stage):
    """Honest about its limits: Latin reports `en`, so romanized Hindi is
    mislabelled here. That is what Phase 2's fastText stage fixes, and why
    FR-3 is verified in Phase 2 rather than now."""
    assert run(stage, "सरकार ने कहा").lang == "hi"
    assert run(stage, "ਸਰਕਾਰ ਨੇ ਕਿਹਾ").lang == "pa"
    assert run(stage, "Sarkar ne kaha ki yeh sach hai").lang == "en"   # known wrong


def test_transliteration_is_not_attempted_in_phase_1(stage):
    assert run(stage, "Sarkar ne kaha").transliterated is None


def test_empty_input_does_not_crash(stage):
    pre = run(stage, "   ")
    assert pre.normalized == ""
