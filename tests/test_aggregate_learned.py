"""The learned aggregator, its features, and the cross-fitting that feeds it
(Phase 6, FR-11 / FR-13, decisions D2-D3). No model weights needed."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

from common.io_jsonl import load_jsonl, write_jsonl
from data.loaders import stance_parent_source_id
from pipeline.aggregate import (
    FEATURE_NAMES,
    VERDICTS,
    AggregatorMismatch,
    LearnedAggregator,
    features,
    softmax,
)
from stance.folds import N_FOLDS, fold_of

ROOT = Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = {"Supports": 0.9, "Refutes": 0.05, "Neutral": 0.05}
R = {"Supports": 0.05, "Refutes": 0.9, "Neutral": 0.05}
N = {"Supports": 0.1, "Refutes": 0.1, "Neutral": 0.8}


# -----------------------------------------------------------------------------
# Folds
# -----------------------------------------------------------------------------


def test_every_answer_of_a_claim_lands_in_its_claims_fold():
    """On the real committed stance split: a claim never straddles two folds."""
    by_claim: dict[str, set[int]] = {}
    for row in load_jsonl(Path("data/splits/averitec_stance/train.jsonl")):
        parent = stance_parent_source_id(row["source_id"])
        by_claim.setdefault(parent, set()).add(fold_of(parent))
    assert all(len(f) == 1 for f in by_claim.values())


def test_folds_are_roughly_balanced_over_real_train_claims():
    claims = [r["source_id"] for r in load_jsonl(Path("data/splits/averitec/train.jsonl"))]
    counts = Counter(fold_of(c) for c in claims)
    assert set(counts) == set(range(N_FOLDS))
    assert all(0.15 <= n / len(claims) <= 0.25 for n in counts.values())


def test_fold_of_refuses_a_stance_row_id():
    with pytest.raises(ValueError, match="CLAIM source_id"):
        fold_of("averitec_stance:train.json:5:q0:a1")


# -----------------------------------------------------------------------------
# Features
# -----------------------------------------------------------------------------


def test_features_have_a_fixed_length_including_no_evidence():
    assert len(features([S, R], [0.7, 0.6])) == len(FEATURE_NAMES)
    assert features([]) == [0.0] * len(FEATURE_NAMES)


def test_features_read_only_the_top_k_passages():
    assert features([S, R, N], k=2) == features([S, R, N, S, S, S], k=2)


def test_features_depend_on_rank_order():
    assert features([S, R]) != features([R, S])


def test_one_refuting_passage_does_not_look_like_nine():
    """The rule's failure: max-over-k lets one passage of ten decide."""
    one = features([S] * 9 + [R])
    nine = features([R] * 9 + [S])
    i = FEATURE_NAMES.index("frac_r50")
    assert one[i] == pytest.approx(0.1) and nine[i] == pytest.approx(0.9)


def test_missing_dense_scores_are_flagged_not_zero_filled_silently():
    f = features([S], [None])
    assert f[FEATURE_NAMES.index("has_dense")] == 0.0


def test_softmax_temperature_flattens():
    hot, cold = softmax([2.0, 0.0], 1.0), softmax([2.0, 0.0], 4.0)
    assert sum(hot) == pytest.approx(1.0) and cold[0] < hot[0]


# -----------------------------------------------------------------------------
# The artifact
# -----------------------------------------------------------------------------


def _artifact(tmp_path: Path, stance: str = "nli", temperature: float = 1.0,
              names=FEATURE_NAMES) -> Path:
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rows = ([S] * 5, [R] * 5, [S, R] * 3, [N] * 5)
    x = [features(r) for r in rows for _ in range(5)]
    y = [v for v in VERDICTS for _ in range(5)]
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    model.fit(x, y)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "model.joblib"
    joblib.dump({"model": model, "features": names, "stance": stance, "k": 10,
                 "temperature": temperature, "classes": VERDICTS}, path)
    return path


def test_learned_aggregator_returns_a_distribution_and_its_argmax(tmp_path):
    agg = LearnedAggregator(path=_artifact(tmp_path))
    out = agg.aggregate([S] * 5)
    assert set(out.probs) == set(VERDICTS)
    assert sum(out.probs.values()) == pytest.approx(1.0)
    assert out.verdict == max(out.probs, key=out.probs.get) == "Supported"
    assert out.confidence == out.probs["Supported"]


def test_temperature_lowers_confidence_without_changing_the_verdict(tmp_path):
    sharp = LearnedAggregator(path=_artifact(tmp_path / "a", temperature=1.0))
    soft = LearnedAggregator(path=_artifact(tmp_path / "b", temperature=5.0))
    a, b = sharp.aggregate([R] * 5), soft.aggregate([R] * 5)
    assert a.verdict == b.verdict and b.confidence < a.confidence


def test_no_passages_is_nei_with_zero_confidence(tmp_path):
    out = LearnedAggregator(path=_artifact(tmp_path)).aggregate([])
    assert (out.verdict, out.confidence) == ("NEI", 0.0)


def test_an_artifact_built_on_other_features_is_refused(tmp_path):
    path = _artifact(tmp_path, names=("something", "else"))
    with pytest.raises(AggregatorMismatch, match="Retrain"):
        LearnedAggregator(path=path).aggregate([S])


def test_orchestrator_refuses_an_aggregator_trained_on_another_stance_model(tmp_path):
    pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    cfg = PipelineConfig(stages={"stance": "always_neutral", "aggregate": "learned"},
                         stage_args={"aggregate": {"path": str(_artifact(tmp_path, "xlmr"))}})
    with pytest.raises(AggregatorMismatch, match="trained on stance 'xlmr'"):
        Orchestrator(cfg)


# -----------------------------------------------------------------------------
# The refusals that keep the training data clean
# -----------------------------------------------------------------------------


def _passages_file(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "passages.jsonl"
    write_jsonl(path, [{"uid": "u0", "source_id": source, "claim": "c",
                        "passages": [{"text": "p", "dense_score": 0.5}]}])
    return path


def test_scoring_train_claims_with_the_model_that_saw_them_is_refused(tmp_path):
    score = _script("score_passages")
    with pytest.raises(SystemExit, match="REFUSED"):
        score.main(["--passages", str(_passages_file(tmp_path, "averitec:train.json:3")),
                    "--stance", "xlmr", "--out", str(tmp_path / "o.jsonl")])


def test_folds_on_dev_claims_are_refused(tmp_path):
    score = _script("score_passages")
    rows = [{"uid": "u0", "source_id": "averitec:train.json:3", "claim": "c", "passages": []},
            {"uid": "u1", "source_id": "averitec:dev.json:3", "claim": "c", "passages": []}]
    path = tmp_path / "mixed.jsonl"
    write_jsonl(path, rows)
    with pytest.raises(SystemExit, match="train claims only"):
        score.main(["--passages", str(path), "--stance", "xlmr", "--folds",
                    "--out", str(tmp_path / "o.jsonl")])


def test_training_on_in_fold_stance_outputs_is_refused(tmp_path):
    train = _script("train_aggregator")
    scored = tmp_path / "scored.jsonl"
    uid = next(iter(load_jsonl(Path("data/splits/averitec/train.jsonl"))))["uid"]
    scored.write_text(json.dumps({"uid": uid, "fold": None, "probs": [S], "dense": [0.5]})
                      + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not cross-fitted"):
        train.main(["--stance", "xlmr", "--train", str(scored), "--dev", str(scored)])


def test_temperature_override_scores_the_same_artifact_unscaled(tmp_path):
    path = _artifact(tmp_path, temperature=5.0)
    assert LearnedAggregator(path=path).temperature == 5.0
    assert LearnedAggregator(path=path, temperature=1.0).temperature == 1.0



def test_without_a_path_the_orchestrator_looks_for_its_stances_artifact(tmp_path, monkeypatch):
    """The served config names only `aggregate: learned`; the artifact must be the
    one trained for the configured stance, never a default that fits another."""
    pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")
    import pipeline.aggregate as agg_mod
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    monkeypatch.setattr(agg_mod, "MODELS", tmp_path)
    orch = Orchestrator(PipelineConfig(stages={"stance": "always_neutral",
                                               "aggregate": "learned"}))
    assert orch.aggregator.path == tmp_path / "aggregator_always_neutral" / "model.joblib"


def test_a_missing_aggregator_degrades_to_the_rule_and_says_so(tmp_path, monkeypatch):
    """SYSTEM_DESIGN 11: degrade, record it, never crash -- CI and a fresh clone
    have no trained artifact."""
    pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")
    import pipeline.aggregate as agg_mod
    from pipeline.orchestrator import Orchestrator, PipelineConfig
    from retrieval.kb import KnowledgeStore

    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d", "is_gold": True, "paragraphs": ["Nursing posts were restored."]}])
    monkeypatch.setattr(agg_mod, "MODELS", tmp_path / "none")
    orch = Orchestrator(PipelineConfig(stages={"stance": "always_neutral",
                                               "aggregate": "learned"}, k=1))
    orch.retriever.store = KnowledgeStore("dev", cache_root=tmp_path)
    trace = orch.verify("Were nursing posts restored?", claim_idx=7)
    assert trace.results[0].verdict == "NEI"
    assert any("no aggregator artifact; rule" in (e.note or "") for e in trace.events)


# -----------------------------------------------------------------------------
# The combined stage: NLI labels shown, both distributions to the aggregator
# -----------------------------------------------------------------------------


def test_one_source_is_exactly_the_plain_features():
    from pipeline.aggregate import multi_features
    assert multi_features([S, R], [0.6, 0.5]) == features([S, R], [0.6, 0.5])


def test_source_view_separates_the_two_models():
    from pipeline.aggregate import source_view
    merged = [{**S, **{"xlmr:" + k: v for k, v in R.items()}}]
    assert source_view(merged, "") == [S]
    assert source_view(merged, "xlmr:") == [R]


def test_combined_stage_shows_nli_and_carries_xlmr_for_the_verdict():
    from stance.combined import CombinedStance
    from stance.nli import StanceResult

    class Fake:
        def __init__(self, probs):
            self.probs = probs

        def label(self, claim, passages):
            best = max(self.probs, key=self.probs.get)
            return [StanceResult(best, self.probs[best], dict(self.probs)) for _ in passages]

    stage = CombinedStance.__new__(CombinedStance)
    stage.nli, stage.xlmr = Fake(N), Fake(R)
    out = stage.label("claim", ["p1", "p2"])
    assert [o.stance for o in out] == ["Neutral", "Neutral"]          # NLI is shown
    assert out[0].probs["xlmr:Refutes"] == R["Refutes"]               # XLM-R carried
    assert out[0].probs["Neutral"] == N["Neutral"]


def test_an_artifact_reading_two_sources_round_trips(tmp_path):
    import joblib
    from sklearn.linear_model import LogisticRegression

    from pipeline.aggregate import feature_names, multi_features

    sources = ("", "xlmr:")
    rows = [[{**a, **{"xlmr:" + k: v for k, v in b.items()}}] * 5
            for a, b in ((S, S), (R, R), (S, R), (N, N))]
    x = [multi_features(r, sources=sources) for r in rows for _ in range(5)]
    y = [v for v in VERDICTS for _ in range(5)]
    path = tmp_path / "m.joblib"
    joblib.dump({"model": LogisticRegression(max_iter=1000).fit(x, y),
                 "features": feature_names(sources), "sources": sources,
                 "stance": "xlmr_nli", "k": 10, "temperature": 1.0,
                 "classes": VERDICTS}, path)
    out = LearnedAggregator(path=path).aggregate(rows[0])
    assert out.verdict == "Supported" and sum(out.probs.values()) == pytest.approx(1.0)
