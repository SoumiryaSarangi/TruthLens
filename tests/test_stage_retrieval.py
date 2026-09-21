"""Retrieval stage tests against a synthetic knowledge store.

Synthetic on purpose: these assert ranking BEHAVIOUR, and a test that depends
on the real 11.5 GB store would be slow, unrunnable in CI, and would change
meaning whenever the data did.
"""

from __future__ import annotations

import pytest

from common.io_jsonl import write_jsonl
from retrieval.kb import KnowledgeStore, claim_index_from_uid

pytest.importorskip("rank_bm25", reason="rank_bm25 is in the ML lock, not the core lock")

from retrieval.bm25 import BM25Retriever
from retrieval.random_retriever import RandomRetriever


@pytest.fixture
def fake_kb(tmp_path, monkeypatch):
    """One claim, 5 documents, exactly one of which is gold and on-topic."""
    cache = tmp_path / "averitec_kb_dev"
    rows = [
        {"doc_id": "d_gold", "is_gold": True,
         "paragraphs": ["Unrelated opener.",
                        "The health minister confirmed 4400 nursing posts were restored."]},
        {"doc_id": "d1", "is_gold": False, "paragraphs": ["A recipe for lemon cake."]},
        {"doc_id": "d2", "is_gold": False, "paragraphs": ["Football results from Tuesday."]},
        {"doc_id": "d3", "is_gold": False, "paragraphs": ["Weather warnings for the coast."]},
        {"doc_id": "d4", "is_gold": False, "paragraphs": ["Share prices fell on Monday."]},
    ]
    write_jsonl(cache / "7.jsonl", rows)
    return tmp_path


def test_bm25_ranks_the_on_topic_gold_document_first(fake_kb):
    r = BM25Retriever(split="dev", k=3)
    r.store = KnowledgeStore("dev", cache_root=fake_kb)
    top = r.topk("were 4400 nursing posts restored by the health minister", 7)
    assert top[0].doc_id == "d_gold"
    assert top[0].score > 0


def test_bm25_respects_k(fake_kb):
    r = BM25Retriever(split="dev", k=10)
    r.store = KnowledgeStore("dev", cache_root=fake_kb)
    assert len(r.topk("nursing posts", 7, k=2)) == 2


def test_bm25_best_paragraph_picks_the_relevant_one_not_the_first(fake_kb):
    """The stance model reads one paragraph; it must be the relevant one."""
    r = BM25Retriever(split="dev", k=3)
    r.store = KnowledgeStore("dev", cache_root=fake_kb)
    doc = r.store.pool(7)[0]
    text, (start, end) = r.best_paragraph("nursing posts restored", doc)
    assert "nursing posts" in text
    assert doc.text[start:end] == text          # offsets address the real span


def test_random_retriever_is_deterministic_under_seed(fake_kb):
    a = RandomRetriever(split="dev", k=3, seed=42)
    b = RandomRetriever(split="dev", k=3, seed=42)
    a.store = b.store = KnowledgeStore("dev", cache_root=fake_kb)
    assert [d.doc_id for d in a.topk("x", 7)] == [d.doc_id for d in b.topk("x", 7)]


def test_random_retriever_changes_with_the_seed(fake_kb):
    a = RandomRetriever(split="dev", k=5, seed=1)
    b = RandomRetriever(split="dev", k=5, seed=2)
    a.store = b.store = KnowledgeStore("dev", cache_root=fake_kb)
    assert [d.doc_id for d in a.topk("x", 7)] != [d.doc_id for d in b.topk("x", 7)]


def test_gold_ids_reads_the_annotation(fake_kb):
    assert KnowledgeStore("dev", cache_root=fake_kb).gold_ids(7) == ["d_gold"]


@pytest.mark.parametrize("source_id,expected", [
    ("averitec:dev.json:133", 133),
    ("averitec:dev.json:0", 0),
])
def test_claim_index_parses_from_source_id(source_id, expected):
    assert claim_index_from_uid(source_id) == expected


def test_claim_index_rejects_a_malformed_source_id():
    with pytest.raises(ValueError, match="claim index"):
        claim_index_from_uid("not-a-source-id")
