"""The faithfulness gate around generated explanations (FR-15, FR-16, FR-18).

Every way generated text can fail must end in the template, with the reason in
the trace. Fake generator and fake NLI, so this runs in CI with no weights.
"""

from __future__ import annotations

import time

import pytest

from common.io_jsonl import write_jsonl
from eval import faithfulness as F
from retrieval.kb import KnowledgeStore

pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")

from pipeline import orchestrator as orch_mod
from pipeline.orchestrator import Orchestrator, PipelineConfig


@pytest.fixture
def kb(tmp_path):
    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d_gold", "is_gold": True,
         "paragraphs": ["The minister restored 4400 nursing posts in 2020."]},
        {"doc_id": "d1", "is_gold": False, "paragraphs": ["Lemon cake recipe."]},
    ])
    return tmp_path


@pytest.fixture(autouse=True)
def word_overlap_nli():
    """Entailed iff every word of the sentence is in the passage."""
    def score(pairs):
        return [1.0 if set(h.lower().rstrip(".").split()) <= set(p.lower().rstrip(".").split())
                else 0.0 for p, h in pairs]
    F.set_scorer(score)
    yield
    F.set_scorer(None)


class FakeGenerator:
    impl = "fake"

    def __init__(self, text="The minister restored 4400 nursing posts in 2020.",
                 delay=0.0, fail=False):
        self.text, self.delay, self.fail = text, delay, fail

    def explain(self, verdict, passages, *, abstained=False, claim=None):
        if self.fail:
            raise RuntimeError("CUDA out of memory")
        time.sleep(self.delay)
        return self.text, []


def make(kb, generator=None, faithfulness="nli", **cfg) -> Orchestrator:
    orch = Orchestrator(PipelineConfig(
        stages={"stance": "always_neutral", "faithfulness": faithfulness}, k=2, **cfg))
    orch.retriever.store = KnowledgeStore("dev", cache_root=kb)
    orch.generator = generator or FakeGenerator()
    return orch


def notes(trace):
    return [e.note or "" for e in trace.events]


def test_an_entailed_explanation_is_served_with_earned_citations(kb):
    res = make(kb).verify("Were nursing posts restored?", claim_idx=7).results[0]
    assert res.explanation_source == "generated"
    assert res.explanation_lang == "en"
    gold = next(p for p in res.passages if p.doc_id == "d_gold")
    assert res.cited == [gold.passage_id]        # cited because NLI entails it
    assert res.faithfulness == 1.0


def test_one_unentailed_sentence_sends_the_template(kb):
    gen = FakeGenerator("The minister restored 4400 nursing posts in 2020. Cats can fly.")
    trace = make(kb, gen).verify("Were nursing posts restored?", claim_idx=7)
    res = trace.results[0]
    assert res.explanation_source == "template"
    assert "Cats" not in res.explanation
    assert any("failed the NLI gate" in n for n in notes(trace))


def test_abstained_verdicts_never_get_generated_prose(kb):
    trace = make(kb, tau_abstain=1.1).verify("Were nursing posts restored?", claim_idx=7)
    assert trace.results[0].explanation_source == "template"
    assert any("abstained" in n for n in notes(trace))


def test_a_generation_error_degrades_to_the_template(kb):
    trace = make(kb, FakeGenerator(fail=True)).verify("Restored?", claim_idx=7)
    assert trace.results[0].explanation_source == "template"
    assert any("generation failed (RuntimeError)" in n for n in notes(trace))


def test_a_slow_generator_times_out_to_the_template(kb, monkeypatch):
    monkeypatch.setattr(orch_mod, "GENERATION_TIMEOUT_S", 0.05)
    trace = make(kb, FakeGenerator(delay=0.5)).verify("Restored?", claim_idx=7)
    assert trace.results[0].explanation_source == "template"
    assert any("generation over" in n for n in notes(trace))


def test_without_a_gate_generated_text_is_never_served(kb):
    trace = make(kb, faithfulness="stub").verify("Restored?", claim_idx=7)
    assert trace.results[0].explanation_source == "template"
    assert any("never served ungated" in n for n in notes(trace))


def test_support_indices_point_at_the_evidence_as_given():
    out = F.support("Posts were restored.", ["", "posts were restored in 2020"])
    assert out["supporting"] == [[1]]


def test_restating_the_claim_under_a_non_supported_verdict_sends_the_template(kb):
    """The rumour, word for word, as the explanation for its own refutation --
    faithful to a passage that asserts it, and exactly wrong to serve."""
    claim = "The minister restored 4400 nursing posts in 2020."
    trace = make(kb, FakeGenerator(claim)).verify(claim, claim_idx=7)
    res = trace.results[0]
    assert res.verdict != "Supported"                 # always_neutral -> NEI
    assert res.explanation_source == "template"
    assert any("restates the claim" in n for n in notes(trace))

