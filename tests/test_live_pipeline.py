"""The live pass inside the orchestrator (post-test Phase 7).

A fake live source and a fake stance model stand in for the network and the
GPU, so what is tested is the pipeline's decisions: when live evidence replaces
an answer, when it must NOT, and what the user is told.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")

from pipeline.contracts import FactCheckMatch
from pipeline.live import LivePassage, LiveResult, live_verdict
from pipeline.orchestrator import Orchestrator, PipelineConfig

S = {"Supports": 0.95, "Refutes": 0.02, "Neutral": 0.03}
R = {"Supports": 0.02, "Refutes": 0.95, "Neutral": 0.03}
N = {"Supports": 0.05, "Refutes": 0.05, "Neutral": 0.90}


# -- the verdict rule ----------------------------------------------------------


def test_strong_support_is_supported():
    verdict, conf, dist = live_verdict([S, S], [0.8, 0.7])
    assert verdict == "Supported" and conf > 0.9 and dist["Refuted"] < 0.05


def test_one_weakly_relevant_refuter_cannot_outvote_three_strong_supporters():
    """The Taj Mahal pattern: the 'Black Taj Mahal' legend page refutes at cosine
    0.65; three pages that support score 0.56-0.68. A max-rule says Conflicting."""
    verdict, _, _ = live_verdict([S, R, S, S], [0.68, 0.65, 0.64, 0.56])
    assert verdict == "Supported"


def test_real_disagreement_is_conflicting():
    verdict, conf, _ = live_verdict([S, R], [0.7, 0.7])
    assert verdict == "Conflicting" and conf > 0.9


def test_neutral_evidence_is_nei_and_no_evidence_is_nei():
    assert live_verdict([N, N], [0.6, 0.6])[0] == "NEI"
    assert live_verdict([], []) == ("NEI", 0.0, {"Supported": 0.0, "Refuted": 0.0,
                                                  "Conflicting": 0.0, "NEI": 1.0})


# -- the orchestrator ----------------------------------------------------------


class FakeLive:
    def __init__(self, result=None, raises=None):
        self.result, self.raises, self.calls = result, raises, 0

    def gather(self, forms, lang):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.result


class FakeStance:
    impl = "fake"

    def __init__(self, probs):
        self.probs = probs

    def label(self, claim, passages):
        return [SimpleNamespace(stance=max(("Supports", "Refutes", "Neutral"),
                                           key=lambda k: self.probs[k]),
                                prob=max(self.probs.values()), probs=self.probs)
                for _ in passages]


def passage(cos=0.7, source="wikipedia", title="Delhi"):
    return LivePassage(f"{title} is the capital.", title, f"https://x/{title}", source, cos, "en")


def make(live=None, enabled=True):
    cfg = PipelineConfig(stages={"stance": "always_neutral"}, live_search=enabled)
    orch = Orchestrator(cfg)
    orch._live = live
    orch.stance = FakeStance(S)
    return orch


def test_live_evidence_replaces_the_offline_answer_and_says_where_it_came_from():
    live = FakeLive(LiveResult(passages=[passage(0.8), passage(0.6, title="India")],
                               sources_used=["wikipedia"]))
    trace = make(live).verify("Delhi is the capital of India", live=True)
    res = trace.results[0]
    assert (res.verdict, res.path, res.explanation_source) == ("Supported", "evidence", "template")
    assert res.live_sources == ["wikipedia"]
    assert {p.source for p in res.passages} == {"wikipedia"} and res.passages[0].stance == "Supports"
    assert any("NOT calibrated" in (e.note or "") for e in trace.events)


def test_a_published_fact_check_of_this_claim_answers_it_on_the_fast_path():
    match = FactCheckMatch(factcheck_id="u", score=0.95, verdict="Refuted", title="No, it does not",
                           url="https://fc/u", publisher="FC", lang="en")
    live = FakeLive(LiveResult(match=match, sources_used=["google_factcheck"]))
    res = make(live).verify("some rumour", live=True).results[0]
    assert (res.path, res.verdict, res.cited) == ("fast", "Refuted", ["u"])
    assert res.live_sources == ["google_factcheck"] and "FC" in res.explanation


def test_nothing_relevant_is_an_honest_not_enough_evidence():
    live = FakeLive(LiveResult(passages=[passage(0.31, title="Britannica")], sources_used=["wikipedia"]))
    trace = make(live).verify("Each student gets Rs 6000", live=True)
    res = trace.results[0]
    assert res.verdict == "NEI" and res.abstained and "nothing relevant" in res.explanation
    assert any("no live source is about this claim" in (e.note or "") for e in trace.events)


def test_a_source_that_is_down_leaves_the_offline_answer_untouched():
    offline = make(FakeLive(LiveResult())).verify("Delhi is the capital of India").results[0]
    down = FakeLive(LiveResult(notes=["degraded: wikipedia unavailable (HTTP 429)"]))
    live = make(down).verify("Delhi is the capital of India", live=True).results[0]
    assert live.model_dump() == offline.model_dump()


def test_a_crash_in_the_live_path_keeps_the_offline_answer_and_records_it():
    offline = make(FakeLive(LiveResult())).verify("Delhi is the capital of India").results[0]
    trace = make(FakeLive(raises=RuntimeError("boom"))).verify("Delhi is the capital of India", live=True)
    assert trace.results[0].model_dump() == offline.model_dump()
    assert any("live search failed (RuntimeError)" in (e.note or "") for e in trace.events)


def test_nothing_is_fetched_unless_the_request_asks():
    live = FakeLive(LiveResult(passages=[passage()]))
    orch = make(live)
    orch.verify("Delhi is the capital of India")                    # live=False, the default
    assert live.calls == 0 and orch._live is live


def test_a_config_without_live_search_refuses_visibly():
    live = FakeLive(LiveResult(passages=[passage()]))
    trace = make(live, enabled=False).verify("Delhi is the capital of India", live=True)
    assert live.calls == 0
    assert any("disabled in this pipeline config" in (e.note or "") for e in trace.events)


def test_an_averitec_claim_never_goes_live():
    live = FakeLive(LiveResult(passages=[passage()]))
    trace = make(live).verify("Were nursing posts restored?", claim_idx=7, live=True)
    assert live.calls == 0
    assert any("free text only" in (e.note or "") for e in trace.events)


def test_the_live_client_is_not_even_built_when_it_is_not_asked_for():
    orch = Orchestrator(PipelineConfig(stages={"stance": "always_neutral"}, live_search=True))
    assert orch._live is None


# -- the API ---------------------------------------------------------------------


def test_the_api_flag_defaults_off_and_is_passed_through(monkeypatch):
    pytest.importorskip("fastapi")
    import app.main as main
    from fastapi.testclient import TestClient

    seen = []
    orch = make(FakeLive(LiveResult()))
    real = orch.verify
    orch.verify = lambda text, claim_idx=None, live=False: (seen.append(live), real(text, claim_idx, live))[1]
    monkeypatch.setattr(main, "_orchestrator", orch)
    monkeypatch.setattr(main, "_config", orch.cfg)
    client = TestClient(main.app)
    client.post("/verify", json={"text": "Delhi is the capital of India"})
    client.post("/verify", json={"text": "Delhi is the capital of India", "live_search": True})
    assert seen == [False, True]
