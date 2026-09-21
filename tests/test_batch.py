"""The batch runner must produce something `make eval` accepts.

SYSTEM_DESIGN.md §1: the served pipeline and the evaluated pipeline are the
same code. This test is what keeps that claim true -- it runs the real
orchestrator over a toy split and feeds the output straight into the real
harness. If the two ever stop fitting together, this fails rather than a
retrieval run silently producing a file nothing can score.
"""

from __future__ import annotations

import pytest
import yaml

from common.io_jsonl import load_jsonl, write_jsonl

pytest.importorskip("rank_bm25")

from eval.evaluate import evaluate
from pipeline.batch import run
from pipeline.orchestrator import PipelineConfig
from retrieval.kb import KnowledgeStore


@pytest.fixture
def toy(tmp_path, monkeypatch):
    """A two-claim split, its text, and a knowledge store with known gold."""
    split = tmp_path / "data" / "splits" / "toy" / "dev.jsonl"
    write_jsonl(split, [
        {"uid": "toy:en:dev:00000", "dataset": "toy", "split": "dev", "lang": "en",
         "script": "latn", "source_id": "toy:dev.json:0", "label": "Supported",
         "label_set": "verdict_5class", "text_sha1": "a" * 40,
         "simhash64": "0" * 16, "n_chars": 30},
        {"uid": "toy:en:dev:00001", "dataset": "toy", "split": "dev", "lang": "en",
         "script": "latn", "source_id": "toy:dev.json:1", "label": "Refuted",
         "label_set": "verdict_5class", "text_sha1": "b" * 40,
         "simhash64": "0" * 16, "n_chars": 30},
    ])
    write_jsonl(tmp_path / "data" / "interim" / "toy" / "dev.jsonl", [
        {"uid": "toy:en:dev:00000", "text": "Nursing posts were restored in 2020."},
        {"uid": "toy:en:dev:00001", "text": "Lemon cake is baked at 180 degrees."},
    ])

    kb = tmp_path / "kb"
    for idx, gold_text in ((0, "The minister restored 4400 nursing posts in 2020."),
                           (1, "Lemon cake bakes at 180 degrees for 40 minutes.")):
        write_jsonl(kb / "averitec_kb_dev" / f"{idx}.jsonl", [
            {"doc_id": f"gold_{idx}", "is_gold": True, "paragraphs": ["Intro.", gold_text]},
            {"doc_id": f"noise_{idx}", "is_gold": False,
             "paragraphs": ["Share prices fell on Monday."]},
        ])

    write_jsonl(tmp_path / "gold.jsonl", [
        {"uid": "toy:en:dev:00000", "relevant_ids": ["gold_0"]},
        {"uid": "toy:en:dev:00001", "relevant_ids": ["gold_1"]},
    ])

    monkeypatch.chdir(tmp_path)
    return tmp_path, split, kb


def _run(toy, stance="always_neutral"):
    tmp, split, kb = toy
    cfg = PipelineConfig(stages={"stance": stance}, k=2)
    import pipeline.batch as batch_mod

    original = batch_mod.Orchestrator

    def patched(config):
        orch = original(config)
        orch.retriever.store = KnowledgeStore("dev", cache_root=kb)
        return orch

    batch_mod.Orchestrator = patched
    try:
        return run(split, cfg, "both",
                   tmp / "preds_r.jsonl", tmp / "preds_v.jsonl")
    finally:
        batch_mod.Orchestrator = original


def test_batch_emits_both_prediction_files(toy):
    tmp, _, _ = toy
    counts = _run(toy)
    assert counts["n"] == 2
    assert len(load_jsonl(tmp / "preds_r.jsonl")) == 2
    assert len(load_jsonl(tmp / "preds_v.jsonl")) == 2


def test_retrieval_predictions_match_the_harness_schema(toy):
    tmp, _, _ = toy
    _run(toy)
    row = load_jsonl(tmp / "preds_r.jsonl")[0]
    assert set(row) == {"uid", "ranked_ids", "scores"}
    assert len(row["ranked_ids"]) == len(row["scores"])


def test_retrieval_output_scores_through_the_real_harness(toy):
    """The whole point: batch output goes straight into `make eval`."""
    tmp, split, _ = toy
    _run(toy)
    cfg = tmp / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({
        "experiment": "toy_retrieval",
        "task": "retrieval",
        "split": str(split).replace("\\", "/"),
        "gold": "gold.jsonl",
        "predictions": "preds_r.jsonl",
        "baseline": "random_rank",
        "metrics": {"retrieval": {"k": [1, 2]}},
        "breakdown": ["lang", "script"],
    }), encoding="utf-8")

    doc = evaluate(cfg, tmp / "results",
                   schema_path=_schema_path())
    assert doc["metrics"]["overall"]["recall@1"] == 1.0, (
        "BM25 should rank the on-topic gold document first for both toy claims"
    )
    assert doc["coverage"]["n_missing"] == 0


def test_verdict_output_scores_through_the_real_harness(toy):
    tmp, split, _ = toy
    _run(toy)
    cfg = tmp / "cfg_v.yaml"
    cfg.write_text(yaml.safe_dump({
        "experiment": "toy_verdict",
        "task": "classification",
        "split": str(split).replace("\\", "/"),
        "predictions": "preds_v.jsonl",
        "label_set": "verdict_5class",
        "baseline": "majority_class",
        "breakdown": ["lang", "script"],
    }), encoding="utf-8")

    doc = evaluate(cfg, tmp / "results", schema_path=_schema_path())
    assert "macro_f1" in doc["metrics"]["overall"]
    assert doc["baseline"]["name"] == "majority_class"


def _schema_path():
    from pathlib import Path
    return Path(__file__).resolve().parents[1] / "configs" / "_schema" / "eval.schema.json"
