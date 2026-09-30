"""The hybrid evidence retriever (FR-9), with a fake encoder and no torch.

The encoder here is a hashed bag of words, L2-normalised, so "similar" means
"shares words" and every expected ranking can be worked out by reading the test.
What is under test is the plumbing -- chunking, fusion, caching, degradation --
not BGE-M3.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pytest

from common.io_jsonl import write_jsonl
from retrieval.bm25 import ScoredDoc
from retrieval.dense_cache import CacheMismatch, ChunkVectorCache
from retrieval.hybrid import HybridRetriever, chunk_spans, fuse, rrf
from retrieval.kb import Document, KnowledgeStore

pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")

DIM = 64


class FakeEncoder:
    """Hashed bag of words. Counts how many texts it was asked to encode."""

    def __init__(self):
        self.calls = 0
        self.texts = 0

    def encode(self, texts, batch_size=32):
        self.calls += 1
        self.texts += len(texts)
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                out[i, int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(norms, 1e-12)


class BrokenEncoder:
    def encode(self, texts, batch_size=32):
        raise RuntimeError("CUDA out of memory")


@pytest.fixture
def kb(tmp_path):
    """One claim. BM25 favours `d_bm25` on a repeated word; the dense side
    favours `d_dense`, whose SECOND paragraph matches the claim's content."""
    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d_bm25", "is_gold": False,
         "paragraphs": ["minister minister minister minister spoke about cricket."]},
        {"doc_id": "d_dense", "is_gold": True,
         "paragraphs": ["An unrelated opening paragraph about the weather.",
                        "The health minister restored 4400 nursing posts."]},
        {"doc_id": "d_other", "is_gold": False, "paragraphs": ["Lemon cake recipe."]},
        {"doc_id": "d_empty", "is_gold": False, "paragraphs": []},
    ])
    return tmp_path


def retriever(kb, tmp_path, encoder=None, **kw) -> HybridRetriever:
    kw.setdefault("cache", "off")
    kw.setdefault("k", min(kw.get("depth", 200), 3))
    r = HybridRetriever(split="dev", cache_root=tmp_path / "vectors", **kw)
    r.store = KnowledgeStore("dev", cache_root=kb)
    r._encoder = encoder or FakeEncoder()
    return r


CLAIM = "health minister restored 4400 nursing posts"


# -----------------------------------------------------------------------------
# Pure pieces
# -----------------------------------------------------------------------------


def test_chunk_spans_address_the_real_document_text():
    """The UI highlights `doc.text[s:e]`, so every span must point at it."""
    doc = Document("d", ("First paragraph.", "", "Second one here.", "Third."), False)
    spans = chunk_spans(doc, chunk_chars=20)
    assert [doc.text[s:e] for s, e in spans] == ["First paragraph.",
                                                 "Second one here.", "Third."]


def test_short_paragraphs_are_packed_into_one_passage():
    doc = Document("d", ("One.", "Two.", "Three."), False)
    assert [doc.text[s:e] for s, e in chunk_spans(doc, 1000)] == ["One. Two. Three."]


def test_an_over_long_paragraph_is_split_at_whitespace():
    doc = Document("d", ("alpha beta gamma delta epsilon",), False)
    pieces = [doc.text[s:e] for s, e in chunk_spans(doc, 12)]
    assert all(len(p) <= 12 for p in pieces)
    assert " ".join(pieces) == "alpha beta gamma delta epsilon"


def test_a_document_with_no_text_has_no_passages():
    assert chunk_spans(Document("d", (), False), 1000) == []
    assert chunk_spans(Document("d", ("   ",), False), 1000) == []


def test_rrf_matches_a_hand_computation():
    """k=60. a: 1/61 + 1/62; b: 1/62 + 1/61; c: 1/63 only."""
    got = rrf([["a", "b", "c"], ["b", "a"]], rrf_k=60)
    assert got["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert got["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert got["c"] == pytest.approx(1 / 63)


def _sd(doc_id, score):
    return ScoredDoc(doc_id, score, Document(doc_id, ("x",), False))


def test_dense_fusion_reorders_by_cosine_and_puts_textless_documents_last():
    fused = fuse([_sd("a", 9.0), _sd("b", 5.0), _sd("c", 1.0)],
                 {"a": 0.1, "b": 0.9, "c": None}, "dense")
    assert [d for d, _ in fused] == ["b", "a", "c"]


def test_weighted_fusion_normalises_bm25_before_mixing():
    """Raw BM25 is unbounded; mixed unnormalised it would drown the cosine."""
    fused = dict(fuse([_sd("a", 100.0), _sd("b", 0.0)], {"a": 0.0, "b": 1.0},
                      "weighted", alpha=0.5))
    assert fused["a"] == pytest.approx(0.5)
    assert fused["b"] == pytest.approx(0.5)


def test_an_unknown_fusion_is_refused():
    with pytest.raises(ValueError, match="fusion"):
        fuse([], {}, "magic")


def test_depth_shallower_than_k_is_refused():
    with pytest.raises(ValueError, match="depth"):
        HybridRetriever(k=10, depth=5, cache="off")


# -----------------------------------------------------------------------------
# Ranking
# -----------------------------------------------------------------------------


def test_topk_is_best_first_with_non_increasing_scores(kb, tmp_path):
    """`src/retrieval/CLAUDE.md`: scores are load-bearing and must be ordered."""
    ranked = retriever(kb, tmp_path, fusion="dense", depth=4, k=4).topk(CLAIM, 7)
    scores = [d.score for d in ranked]
    assert scores == sorted(scores, reverse=True)


class ParaphraseEncoder:
    """Knows that "reinstated nurse jobs" means "restored nursing posts".

    A bag-of-words encoder cannot separate dense from BM25 -- both are lexical --
    so this one maps the query and one paraphrase to the same direction and
    everything else to an orthogonal one. That is the situation dense retrieval
    exists for: a relevant passage sharing no words with the claim.
    """

    def encode(self, texts, batch_size=32):
        out = np.zeros((len(texts), 2), dtype=np.float32)
        for i, text in enumerate(texts):
            same = text == PARAPHRASE_QUERY or "reinstated" in text
            out[i, 0 if same else 1] = 1.0
        return out


PARAPHRASE_QUERY = "nursing posts restored"


def test_dense_rerank_promotes_a_paraphrase_bm25_cannot_see(tmp_path):
    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "a_lexical", "is_gold": False,
         "paragraphs": ["nursing posts restored at the cricket ground, posts"]},
        {"doc_id": "b_paraphrase", "is_gold": True,
         "paragraphs": ["The ministry reinstated four thousand nurse jobs."]},
        {"doc_id": "c_other", "is_gold": False, "paragraphs": ["Lemon cake."]},
    ])
    r = retriever(tmp_path, tmp_path, encoder=ParaphraseEncoder(), fusion="dense",
                  depth=3, k=3)
    bm25 = [d.doc_id for d in r._bm25.topk(PARAPHRASE_QUERY, 7, 3)]
    ranked = r.topk(PARAPHRASE_QUERY, 7)
    assert bm25[0] == "a_lexical", "the fixture must put BM25 on the wrong answer"
    assert ranked[0].doc_id == "b_paraphrase"
    assert ranked[0].dense_score == pytest.approx(1.0)


def test_a_document_outside_bm25_top_n_never_appears(kb, tmp_path):
    """The reranker reorders BM25's top N; it does not search the pool."""
    r = retriever(kb, tmp_path, fusion="dense", depth=2, k=2)
    allowed = {d.doc_id for d in r._bm25.topk(CLAIM, 7, 2)}
    assert {d.doc_id for d in r.topk(CLAIM, 7)} <= allowed


def test_best_paragraph_is_the_passage_that_matched(kb, tmp_path):
    """MaxP: the stance model reads the passage the retriever matched, not the
    first paragraph and not one chosen by a different rule."""
    r = retriever(kb, tmp_path, chunk_chars=60)
    doc = next(d for d in r.store.pool(7) if d.doc_id == "d_dense")
    text, (start, end) = r.best_paragraph(CLAIM, doc)
    assert "nursing posts" in text
    assert "weather" not in text
    assert doc.text[start:end] == text


# -----------------------------------------------------------------------------
# Degradation (NFR-7)
# -----------------------------------------------------------------------------


def test_an_encoder_failure_degrades_to_bm25_and_says_so(kb, tmp_path):
    r = retriever(kb, tmp_path, encoder=BrokenEncoder(), depth=4, k=3)
    ranked = r.topk(CLAIM, 7)
    assert [d.doc_id for d in ranked] == [d.doc_id for d in r._bm25.topk(CLAIM, 7, 3)]
    assert ranked.note.startswith("degraded: dense->bm25")


def test_a_failed_model_load_is_not_retried_on_every_claim(kb, tmp_path, monkeypatch):
    """A missing model should cost one failed load, not one per claim."""
    import retrieval.encoders as encoders

    attempts = []

    def fail(name, **kw):
        attempts.append(name)
        raise OSError("no such model")

    monkeypatch.setattr(encoders, "build_encoder", fail)
    r = HybridRetriever(split="dev", depth=4, k=3, cache="off")
    r.store = KnowledgeStore("dev", cache_root=kb)
    r.topk(CLAIM, 7)
    r.topk(CLAIM, 7)
    assert attempts == ["bge_m3"]


def test_best_paragraph_goes_lexical_after_a_load_failure(kb, tmp_path):
    r = retriever(kb, tmp_path, encoder=BrokenEncoder(), depth=4)
    r._encoder_error = RuntimeError("no model")
    doc = next(d for d in r.store.pool(7) if d.doc_id == "d_dense")
    text, _ = r.best_paragraph(CLAIM, doc)
    assert "nursing posts" in text


# -----------------------------------------------------------------------------
# The vector cache: encode once, ablate for free
# -----------------------------------------------------------------------------


def test_a_second_run_reads_the_cache_and_encodes_only_the_query(kb, tmp_path):
    first = retriever(kb, tmp_path, cache="readwrite", depth=4)
    first.topk(CLAIM, 7)
    second = retriever(kb, tmp_path, cache="readwrite", depth=4)
    second.topk(CLAIM, 7)
    assert second._encoder.texts == 1              # the query, nothing else


def test_a_shallower_depth_after_a_deeper_one_encodes_no_documents(kb, tmp_path):
    """The whole point of keying by document: N=100 after N=500 is a pure read."""
    retriever(kb, tmp_path, cache="readwrite", depth=4).topk(CLAIM, 7)
    shallow = retriever(kb, tmp_path, cache="readwrite", depth=2, k=2)
    shallow.topk(CLAIM, 7)
    assert shallow._encoder.texts == 1


def test_changed_document_text_is_reencoded(kb, tmp_path):
    """A stale vector for edited text would score the wrong words."""
    retriever(kb, tmp_path, cache="readwrite", depth=4).topk(CLAIM, 7)
    write_jsonl(kb / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d_dense", "is_gold": True,
         "paragraphs": ["Entirely new text about nursing posts."]},
    ])
    again = retriever(kb, tmp_path, cache="readwrite", depth=1, k=1)
    again.topk(CLAIM, 7)
    assert again._encoder.texts == 2               # query + the changed passage


def test_a_cache_built_with_other_settings_refuses(tmp_path):
    """Vectors from another passage length are not comparable with this query."""
    ChunkVectorCache(kb_split="dev", encoder="bge_m3", max_length=256,
                     chunk_chars=1000, max_doc_chars=4000, root=tmp_path).load(0)
    other = ChunkVectorCache(kb_split="dev", encoder="bge_m3", max_length=256,
                             chunk_chars=500, max_doc_chars=4000, root=tmp_path)
    other.dir = next(tmp_path.iterdir())           # point it at the first cache
    with pytest.raises(CacheMismatch, match="chunk_chars"):
        other.load(0)
