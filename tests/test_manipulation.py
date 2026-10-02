"""FR-19 manipulation flags: what each rule sees, and that no flag moves a verdict.

The NLI half is exercised with a fake scorer; the real model is GPU-only and
its threshold is untuned by design (there is no gold to tune it on).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from manipulation.flags import MAX_FLAGS, NoFlags, RulesNLIFlags, rule_flags


@pytest.mark.parametrize("text, label", [
    ("Share this urgent message before it is deleted", "Appeal_to_Time"),
    ("yeh message turant sab groups mein bhejo", "Appeal_to_Time"),
    ("ਇਹ ਸੁਨੇਹਾ ਜਲਦੀ ਭੇਜੋ", "Appeal_to_Time"),
    ("WHO has confirmed that garlic cures the virus", "Appeal_to_Authority"),
    ("डॉक्टरों का कहना है कि नींबू पानी से कैंसर ठीक होता है", "Appeal_to_Authority"),
    ("Everyone knows the vaccine has a chip", "Appeal_to_Popularity"),
    ("sab log keh rahe hain ki paani mehnga hoga", "Appeal_to_Popularity"),
    ("Hot water kills the virus!!", "Loaded_Language"),
    ("🚨 new rule from tomorrow", "Loaded_Language"),
    ("THIS IS VERY IMPORTANT NEWS", "Loaded_Language"),
    ("ਇਹ ਖਤਰਨਾਕ ਹੈ", "Loaded_Language"),
    ("stop the fake news. stop the fake news. stop the fake news.", "Repetition"),
])
def test_each_rule_fires_on_its_own_example(text, label):
    assert label in rule_flags(text)


def test_who_the_pronoun_is_not_who_the_organisation():
    assert "Appeal_to_Authority" not in rule_flags("people who drink water live longer")


def test_romanized_input_meets_the_native_keyword_list_through_its_transliteration():
    assert "Appeal_to_Time" in rule_flags("ekdum alag likha hai", transliterated="तुरंत भेजो")


@pytest.mark.parametrize("greeting", [
    "Good morning, stay blessed 🙏",
    "सुप्रभात, आपका दिन शुभ हो",
    "ਸ਼ੁਭ ਸਵੇਰ ਜੀ",
])
def test_a_greeting_is_not_flagged(greeting):
    assert RulesNLIFlags(use_nli=False).flags(greeting) == []


class FakeNLI:
    """P(Supports) per hypothesis, by substring."""

    def __init__(self, scores: dict[str, float]):
        self.scores = scores

    def score_pairs(self, pairs):
        out = []
        for _premise, hypothesis in pairs:
            p = next((v for k, v in self.scores.items() if k in hypothesis), 0.0)
            out.append(SimpleNamespace(probs={"Supports": p}))
        return out


def test_nli_flags_only_above_its_threshold():
    flagger = RulesNLIFlags(nli=FakeNLI({"frighten": 0.95, "exaggerated": 0.6}))
    assert flagger.flags("plain text") == ["Appeal_to_Fear-Prejudice"]


def test_at_most_three_flags_in_a_fixed_order():
    flagger = RulesNLIFlags(nli=FakeNLI({"frighten": 0.99, "exaggerated": 0.99}))
    text = "URGENT!! WHO says everyone knows this DANGEROUS cure"
    flags = flagger.flags(text)
    assert len(flags) == MAX_FLAGS
    assert flags[0] == "Appeal_to_Fear-Prejudice"


def test_the_default_impl_flags_nothing():
    assert NoFlags().flags("URGENT!! share now") == []


# -----------------------------------------------------------------------------
# Wired into the orchestrator: flags are attached, verdicts are untouched
# -----------------------------------------------------------------------------


@pytest.fixture
def kb(tmp_path):
    pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")
    from common.io_jsonl import write_jsonl

    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d_gold", "is_gold": True,
         "paragraphs": ["Intro.", "The minister restored 4400 nursing posts in 2020."]},
    ])
    return tmp_path


def _orchestrator(kb_root, manipulation: str):
    from pipeline.orchestrator import Orchestrator, PipelineConfig
    from retrieval.kb import KnowledgeStore

    stages = {"stance": "always_neutral", "manipulation": manipulation}
    orch = Orchestrator(PipelineConfig(stages=stages,
                                       stage_args={"manipulation": {"use_nli": False}}
                                       if manipulation == "rules_nli" else {}))
    orch.retriever.store = KnowledgeStore("dev", cache_root=kb_root)
    return orch


def test_flags_never_change_the_verdict(kb):
    text = "URGENT!! Were 4400 nursing posts restored? Share before it is deleted"
    off = _orchestrator(kb, "none").verify(text, claim_idx=7).results[0]
    on = _orchestrator(kb, "rules_nli").verify(text, claim_idx=7).results[0]
    assert off.manipulation_flags == []
    assert "Appeal_to_Time" in on.manipulation_flags
    for field in ("verdict", "confidence", "abstained", "explanation", "verdict_probs"):
        assert getattr(on, field) == getattr(off, field), field


def test_a_failing_flagger_degrades_to_no_flags(kb):
    orch = _orchestrator(kb, "rules_nli")

    def boom(*_a, **_k):
        raise RuntimeError("model gone")

    orch.manipulation.flags = boom
    trace = orch.verify("URGENT!! nursing posts", claim_idx=7)
    assert trace.results[0].manipulation_flags == []
    assert any(e.stage == "manipulation" and "degraded" in (e.note or "")
               for e in trace.events)
