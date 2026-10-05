"""The polarity guard on fact-check matches (docs/polarity-guard-v2-protocol.md).

Fake sources and a fake NLI model stand in for the network and the GPU: what is tested is the decision. A match whose fact-checked claim the NLI model
reads as CONTRADICTING the user's claim is blocked and the claim falls through, as if nothing had matched; entailment, neutral, an unchecked language
and a switched-off guard all let the match stand.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")

from pipeline.contracts import FactCheckMatch
from pipeline.live import LiveResult
from pipeline.orchestrator import Orchestrator, PipelineConfig

CONTRADICTS = {"Supports": 0.01, "Refutes": 0.98, "Neutral": 0.01}
ENTAILS = {"Supports": 0.97, "Refutes": 0.01, "Neutral": 0.02}
NEUTRAL = {"Supports": 0.05, "Refutes": 0.05, "Neutral": 0.90}


class FakeLive:
    def __init__(self, result):
        self.result = result

    def gather(self, forms, lang):
        return self.result


class RecordingStance:
    impl = "fake"

    def __init__(self, probs):
        self.probs, self.pairs = probs, []

    def label(self, claim, passages):
        self.pairs.extend((claim, p) for p in passages)
        return [SimpleNamespace(stance="x", prob=0.9, probs=self.probs) for _ in passages]


class FakeTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, text, src, dst):
        self.calls.append((text, src, dst))
        return "Pineapple juice can cure blood cancer."

    def to_english(self, text, lang):
        return text


def match(lang="en", text="Pineapple juice can cure blood cancer", score=0.95):
    return FactCheckMatch(factcheck_id="u", score=score, verdict="Refuted", title="No, it cannot", url="https://fc/u", publisher="FC",
                          lang=lang, claim_text=text)


def make(live_match=None, guard=True, probs=CONTRADICTS, offline_match=None):
    cfg = PipelineConfig(stages={"stance": "always_neutral"}, live_search=True, live_verdict=True, live_match_guard=guard)
    orch = Orchestrator(cfg)
    orch._live = FakeLive(LiveResult(match=live_match, sources_used=["google_factcheck"]))
    orch.stance = RecordingStance(probs)
    orch._live_nli = orch.stance                        # the live NLI model is the same fake
    orch._translator = FakeTranslator()
    if offline_match is not None:
        orch.matcher = SimpleNamespace(impl="fake", top1=lambda claim: offline_match)
    return orch


def verify(orch, text="Pineapple juice cannot cure blood cancer.", live=True):
    trace = orch.verify(text, live=live)
    return trace.results[0], trace


def notes(trace):
    return " | ".join(e.note or "" for e in trace.events)


def test_a_live_match_that_the_nli_model_reads_as_contradicting_is_blocked_and_the_claim_falls_through():
    orch = make(match())
    res, trace = verify(orch)
    assert res.path != "fast" and res.cited != ["u"]
    assert "BLOCKED" in notes(trace) and "P(contradiction) 0.98" in notes(trace)
    assert orch.stance.pairs == [("Pineapple juice cannot cure blood cancer.", "Pineapple juice can cure blood cancer")]   # premise = the matched claim


def test_a_live_match_that_is_entailed_or_neutral_stands():
    for probs in (ENTAILS, NEUTRAL):
        res, trace = verify(make(match(), probs=probs), text="Pineapple juice can cure blood cancer.")
        assert (res.path, res.verdict, res.cited) == ("fast", "Refuted", ["u"]) and "kept" in notes(trace)


def test_with_the_guard_off_the_match_stands_whatever_the_model_says_and_the_model_is_not_asked():
    orch = make(match(), guard=False)
    res, _ = verify(orch)
    assert (res.path, res.verdict) == ("fast", "Refuted") and orch.stance.pairs == []


def test_a_hindi_matched_claim_is_translated_to_english_before_the_check():
    orch = make(match(lang="hi", text="अनानास का जूस ब्लड कैंसर ठीक कर सकता है"))
    res, trace = verify(orch)
    assert orch._translator.calls == [("अनानास का जूस ब्लड कैंसर ठीक कर सकता है", "hi", "en")]
    assert orch.stance.pairs[0][1] == "Pineapple juice can cure blood cancer." and "BLOCKED" in notes(trace) and res.path != "fast"


def test_a_match_in_another_language_is_not_checked_and_stands():
    orch = make(match(lang="other", text="El jugo de piña cura el cáncer"))
    res, trace = verify(orch)
    assert (res.path, res.verdict) == ("fast", "Refuted") and "not checked (language)" in notes(trace) and orch.stance.pairs == []


def test_a_match_with_no_claim_text_is_not_checked_and_stands():
    res, trace = verify(make(match(text=None)))
    assert res.path == "fast" and "not checked (no claim text" in notes(trace)


def test_a_failing_model_keeps_the_match_and_says_so():
    orch = make(match())

    class Boom:
        impl = "boom"

        def label(self, claim, passages):
            raise RuntimeError("gpu gone")

    orch._live_nli = orch.stance = Boom()
    res, trace = verify(orch)
    assert res.path == "fast" and "polarity guard failed" in notes(trace)


def test_the_offline_fast_path_match_is_guarded_too():
    orch = make(live_match=None, offline_match=match(score=0.95))
    res, trace = verify(orch, live=False)
    assert res.path != "fast" and "BLOCKED" in notes(trace)
    kept, _ = verify(make(live_match=None, offline_match=match(score=0.95), probs=ENTAILS), text="Pineapple juice can cure blood cancer.", live=False)
    assert kept.path == "fast"


def test_the_guard_is_off_by_default_in_the_config_class_and_the_served_key_is_a_bool():
    assert PipelineConfig().live_match_guard is False and "live_match_guard" not in PipelineConfig().describe()
    # The served config's value is the protocol's decision (docs/polarity-guard-v2-protocol.md): it is on only while the rule is measured
    # and stays on only if the rule passes, so the test pins that the key exists and is a bool, not a value.
    assert isinstance(PipelineConfig.load("configs/pipeline/dev.yaml").live_match_guard, bool)
    assert PipelineConfig(live_match_guard=True).describe()["live_match_guard"] is True
