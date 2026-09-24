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


# -----------------------------------------------------------------------------
# BM25 over the global fact-check pool (FR-8)
# -----------------------------------------------------------------------------
# `rank_bm25` is the independent oracle here, the way scikit-learn is for the
# classification metrics. The implementation under test replaces it for speed --
# it precomputes every (document, term) weight, which Okapi BM25 allows because
# it ignores query-term weighting -- so the thing worth checking is that the
# arithmetic did not change along with the data structure.

TOY_CORPUS = [
    ["sarkar", "ne", "kaha", "6000", "rupaye", "milenge"],
    ["sarkar", "ne", "kaha", "kuch", "nahi"],
    ["vaccine", "se", "khatra", "hai"],
    ["sarkar", "sarkar", "sarkar"],
    ["completely", "unrelated", "text", "about", "cricket"],
]


def _retriever(tmp_path, corpus=TOY_CORPUS, ids=None):
    from common.io_jsonl import write_jsonl
    from retrieval.factcheck_bm25 import FactCheckBM25Retriever

    ids = ids or [f"fc{i}" for i in range(len(corpus))]
    write_jsonl(tmp_path / "bm25_corpus.jsonl",
                [{"id": i, "tokens": t} for i, t in zip(ids, corpus, strict=True)])
    return FactCheckBM25Retriever(k=5, index_dir=tmp_path)


@pytest.mark.parametrize("query", [
    ["sarkar"],
    ["sarkar", "ne", "kaha"],
    ["vaccine", "khatra"],
    ["sarkar", "sarkar"],            # a repeated query term must count twice
    ["nonexistent"],
    ["sarkar", "nonexistent"],
])
def test_scores_agree_with_rank_bm25(tmp_path, query):
    """The independent oracle. A different data structure, the same arithmetic."""
    rank_bm25 = pytest.importorskip("rank_bm25")

    theirs = rank_bm25.BM25Okapi(TOY_CORPUS).get_scores(query)
    ours = _retriever(tmp_path).scores(query)
    assert ours == pytest.approx(theirs, abs=1e-4)


def test_a_term_in_most_of_the_corpus_keeps_its_idf_floor(tmp_path):
    """BM25Okapi replaces a negative IDF with EPSILON * average_idf rather than
    letting a near-universal term subtract from every score. Dropping that floor
    is the easiest way to silently disagree with the oracle."""
    rank_bm25 = pytest.importorskip("rank_bm25")

    corpus = [["common", "a"], ["common", "b"], ["common", "c"], ["rare", "d"]]
    theirs = rank_bm25.BM25Okapi(corpus).get_scores(["common"])
    ours = _retriever(tmp_path, corpus, ids=["w", "x", "y", "z"]).scores(["common"])
    assert ours == pytest.approx(theirs, abs=1e-4)
    assert (ours[:3] > 0).all(), "the floor should keep these positive"


def test_ranking_is_best_first_and_carries_the_score(tmp_path):
    ranked = _retriever(tmp_path).rank_batch(["sarkar ne kaha"], k=3)[0]
    assert [d.doc_id for d in ranked][:1] == ["fc1"] or ranked[0].score > 0
    assert [d.score for d in ranked] == sorted((d.score for d in ranked), reverse=True)


def test_a_query_with_no_lexical_content_returns_nothing(tmp_path):
    """Zeros ranked by id would be a silent arbitrary ranking presented as a
    result. An empty list is the honest answer and the harness refuses it."""
    assert _retriever(tmp_path).rank_batch(["!!! ???"], k=3)[0] == []


def test_a_query_of_only_unknown_terms_scores_everything_zero(tmp_path):
    """Distinct from the case above: there ARE tokens, none are in the vocabulary.
    Every document is equally (ir)relevant, which is a real answer."""
    ranked = _retriever(tmp_path).rank_batch(["zzz yyy"], k=3)[0]
    assert len(ranked) == 3
    assert all(d.score == 0.0 for d in ranked)


def test_topk_ignores_claim_idx_so_it_swaps_with_the_averitec_retriever(tmp_path):
    """The pool here is global; the signature matches only so the registry can
    interchange the two."""
    retriever = _retriever(tmp_path)
    assert retriever.topk("sarkar", claim_idx=7) == retriever.topk("sarkar")


def test_a_missing_index_refuses_and_says_how_to_build_it(tmp_path):
    from retrieval.factcheck_bm25 import FactCheckBM25Retriever

    with pytest.raises(RuntimeError, match="build_factcheck_bm25"):
        FactCheckBM25Retriever(index_dir=tmp_path / "empty").rank_batch(["x"])
