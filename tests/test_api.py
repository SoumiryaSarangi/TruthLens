"""API tests. SYSTEM_DESIGN.md §8 and §12.

Skipped when fastapi is absent, which is the case in CI (it lives in the ML
lock). They use the always_neutral stance so no weights are needed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="fastapi is in the ML lock, not the core lock")
pytest.importorskip("rank_bm25")

from fastapi.testclient import TestClient

from common.io_jsonl import write_jsonl
from pipeline.orchestrator import Orchestrator, PipelineConfig
from retrieval.kb import KnowledgeStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.main as main

    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d_gold", "is_gold": True,
         "paragraphs": ["Intro.", "The minister restored 4400 nursing posts."]},
    ])
    cfg = PipelineConfig(stages={"stance": "always_neutral"})
    orch = Orchestrator(cfg)
    orch.retriever.store = KnowledgeStore("dev", cache_root=tmp_path)

    monkeypatch.setattr(main, "_orchestrator", orch)
    monkeypatch.setattr(main, "_config", cfg)
    return TestClient(main.app)


# -----------------------------------------------------------------------------
# /verify
# -----------------------------------------------------------------------------


def test_verify_returns_the_documented_shape(client):
    r = client.post("/verify?claim_idx=7", json={"text": "Were nursing posts restored?"})
    assert r.status_code == 200
    body = r.json()
    for key in ("request_id", "input", "checkworthy", "results", "unchecked_claims", "trace"):
        assert key in body
    result = body["results"][0]
    for key in ("claim", "path", "verdict", "confidence", "abstained",
                "explanation", "explanation_source", "cited", "passages"):
        assert key in result


def test_verify_rejects_empty_text(client):
    """FR-1: empty input is a validation error, never a verdict."""
    assert client.post("/verify", json={"text": "   "}).status_code == 422


def test_verify_rejects_missing_text(client):
    assert client.post("/verify", json={}).status_code == 422


def test_verify_rejects_overlong_text(client):
    assert client.post("/verify", json={"text": "x" * 5000}).status_code == 422


def test_free_text_abstains_rather_than_guessing(client):
    """No demo corpus yet, so a claim with no pool must not get a verdict."""
    body = client.post("/verify", json={"text": "The sky is green."}).json()
    res = body["results"][0]
    assert res["verdict"] == "NEI" and res["abstained"] is True


def test_trace_can_be_suppressed(client):
    body = client.post("/verify?claim_idx=7",
                       json={"text": "nursing posts", "include_trace": False}).json()
    assert "trace" not in body


# -----------------------------------------------------------------------------
# /health and /version
# -----------------------------------------------------------------------------


def test_health_reports_each_stage(client):
    body = client.get("/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert "retrieval" in body["stages"] and "stance" in body["stages"]


def test_version_reports_taus_and_confidence_bands(client):
    """FR-21 + UI_UX.md §7: the UI may not hard-code the band cut points."""
    body = client.get("/version").json()
    assert "tau_match" in body and "tau_abstain" in body
    assert set(body["confidence_bands"]) == {"high", "medium"}
    assert body["config"]["stages"]["retrieval"] == "bm25"


def test_index_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "TruthLens" in r.text
