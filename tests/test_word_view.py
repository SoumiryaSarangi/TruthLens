"""The on-demand "which words mattered" view (docs/word-highlight-protocol.md): the pure helpers, the
explainer with fake NLI models, the faithfulness gates, and the endpoint. No model is loaded."""
from __future__ import annotations

import pytest

from eval.metrics import word_faithfulness_metrics
from explain.occlusion import (
    bottom_indices,
    influences,
    source_sentences,
    split_words,
    top_indices,
    without,
)
from explain.words import explain_words
from stance.nli import StanceResult


def test_words_are_whitespace_tokens_and_removal_keeps_the_rest_in_order():
    words = split_words("Paris is the capital of France")
    assert words == ["Paris", "is", "the", "capital", "of", "France"]
    assert without(words, [1, 4]) == "Paris the capital France"
    assert without(words, []) == "Paris is the capital of France"


def test_only_words_that_pushed_toward_the_verdict_are_marked_and_ties_go_to_the_earlier_word():
    assert top_indices([0.0, 0.3, -0.2, 0.3, 0.1], k=2) == [1, 3]
    assert top_indices([0.0, -0.1, 0.0]) == []                 # nothing mattered: no made-up highlight
    assert top_indices([0.5], k=3) == [0]
    assert bottom_indices([0.4, -0.3, 0.0, 0.2], k=2) == [1, 2]


def test_influence_is_the_drop_in_probability():
    assert influences(0.9, [0.9, 0.4, 0.95]) == pytest.approx([0.0, 0.5, -0.05])


def test_the_source_is_split_into_at_most_two_sentences():
    assert source_sentences("Paris is in France. It is the capital. Extra one.") == ["Paris is in France.", "It is the capital."]
    assert source_sentences("") == []


class _FakeNLI:
    """P(Refutes) is high only while the word 'not' is in the claim and 'Paris' is in the premise."""

    def score_pairs(self, pairs):
        out = []
        for premise, hypothesis in pairs:
            p = 0.1 + (0.6 if "not" in hypothesis.split() else 0.0) + (0.2 if "Paris" in premise else 0.0)
            out.append(StanceResult("Refutes", p, {"Supports": 1 - p, "Refutes": p, "Neutral": 0.0}))
        return out


def test_the_word_that_carries_the_verdict_is_the_top_word_and_the_right_sentence_is_marked():
    out = explain_words([_FakeNLI(), _FakeNLI()], "Paris is not the capital", "Paris is a city. Lyon is large.", "Refuted")
    assert [out["words"][i]["word"] for i in out["top"]] == ["not"]     # the only claim word the models used
    marked = [s["text"] for s in out["sentences"] if s["marked"]]
    assert marked == ["Paris is a city."]
    assert out["p_verdict"] == pytest.approx(0.9)


def test_a_word_view_is_refused_for_anything_but_a_supported_or_refuted_verdict():
    for verdict in ("NEI", "Conflicting", "NotAClaim"):
        with pytest.raises(ValueError):
            explain_words([_FakeNLI()], "x y z", "p", verdict)


def test_the_faithfulness_gates_pass_when_the_top_words_matter_and_fail_when_they_do_not():
    good = word_faithfulness_metrics([0.5] * 10, [0.1] * 10, [0.0] * 10)
    assert good["passes"] and good["win_rate"] == 1.0 and good["mean_ratio"] == pytest.approx(5.0)
    same = word_faithfulness_metrics([0.2] * 10, [0.2] * 10, [0.2] * 10)
    assert not same["passes"] and not same["gates"]["win_rate"]
    # the ratio gate alone: wins every claim but by too little
    thin = word_faithfulness_metrics([0.11] * 10, [0.1] * 10, [0.0] * 10)
    assert thin["gates"]["win_rate"] and not thin["gates"]["mean_ratio"] and not thin["passes"]
    # a ranking that is only "long claims lose more": the bottom words hurt more than random ones
    bad_bottom = word_faithfulness_metrics([0.5] * 10, [0.1] * 10, [0.3] * 10)
    assert not bad_bottom["gates"]["bottom_not_above_random"] and not bad_bottom["passes"]


def test_the_faithfulness_bootstrap_is_seeded():
    a = word_faithfulness_metrics([0.5, 0.2, 0.4, 0.1], [0.1, 0.2, 0.1, 0.3], [0.0] * 4)
    b = word_faithfulness_metrics([0.5, 0.2, 0.4, 0.1], [0.1, 0.2, 0.1, 0.3], [0.0] * 4)
    assert a == b


def test_the_faithfulness_metric_refuses_mismatched_inputs():
    with pytest.raises(ValueError):
        word_faithfulness_metrics([0.1], [0.1, 0.2], [0.1])
    with pytest.raises(ValueError):
        word_faithfulness_metrics([], [], [])


# --- the endpoint

pytest.importorskip("fastapi")


def test_the_endpoint_is_404_when_the_word_view_is_off_and_422_for_a_verdict_it_cannot_explain(monkeypatch):
    import app.main as main
    from fastapi.testclient import TestClient

    class Off:
        def explain_words(self, *a):
            raise LookupError("the word view is not enabled")

    monkeypatch.setattr(main, "get_orchestrator", lambda: Off())
    client = TestClient(main.app)
    body = {"claim": "Paris is not the capital", "premise": "Paris is a city.", "verdict": "Refuted"}
    assert client.post("/explain_words", json=body).status_code == 404
    assert client.post("/explain_words", json={**body, "verdict": "NEI"}).status_code == 422
    assert client.post("/explain_words", json={**body, "claim": ""}).status_code == 422


def test_the_endpoint_returns_the_explanation_and_503_when_the_models_fail(monkeypatch):
    import app.main as main
    from fastapi.testclient import TestClient

    class On:
        def explain_words(self, claim, premise, verdict):
            return {"verdict": verdict, "claim": claim, "top": [0]}

    class Broken:
        def explain_words(self, *a):
            raise RuntimeError("model unavailable")

    body = {"claim": "Paris is not the capital", "premise": "Paris is a city.", "verdict": "Refuted"}
    monkeypatch.setattr(main, "get_orchestrator", lambda: On())
    assert TestClient(main.app).post("/explain_words", json=body).json()["top"] == [0]
    monkeypatch.setattr(main, "get_orchestrator", lambda: Broken())
    assert TestClient(main.app).post("/explain_words", json=body).status_code == 503
