"""The embedding ladder and the dense retriever (Phase 2 claim matching).

The neural rungs need weights and are marked `gpu`. Everything that can be
checked without them is checked without them, because the bugs that matter here
-- wrong pooling, unnormalised vectors, a query space that is not the document
space -- are all shape-and-arithmetic bugs that a 4-document fixture catches
just as well as 78,077 real ones.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from retrieval.dense import DenseRetriever
from retrieval.encoders import LADDER, build_encoder, l2_normalize

CORPUS = [
    "The government announced a new scheme for farmers this year",
    "Turmeric milk cures every disease within two days, doctors will not say",
    "Mobile tower radiation is killing birds across the city",
    "A lucky customer scheme offers five thousand rupees cashback",
]


def test_ladder_order_is_cheapest_first():
    """The report reads in this order, so a reordering is a content change."""
    assert LADDER == ("tfidf", "word2vec", "muril", "labse", "bge_m3")


def test_build_encoder_rejects_an_unknown_name():
    with pytest.raises(ValueError, match="unknown encoder"):
        build_encoder("not-an-encoder")


def test_l2_normalize_makes_rows_unit_length():
    """Inner product is only cosine similarity if this holds."""
    matrix = np.array([[3.0, 4.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    out = l2_normalize(matrix)
    assert out[0] == pytest.approx([0.6, 0.8])
    assert np.linalg.norm(out[1]) == pytest.approx(1.0)
    # A zero row must not become NaN -- an empty document is legal input and a
    # single NaN propagates through the whole score matrix.
    assert not np.isnan(out[2]).any()


def test_tfidf_encoder_produces_normalised_vectors():
    encoder = build_encoder("tfidf", dim=3)
    encoder.fit(CORPUS)
    vectors = encoder.encode(CORPUS)
    assert vectors.shape == (4, 3)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_tfidf_refuses_to_encode_before_it_is_fitted():
    """A silently unfitted vectoriser would put queries in a different space."""
    encoder = build_encoder("tfidf", dim=3)
    with pytest.raises(RuntimeError, match="fit must be called"):
        encoder.encode(CORPUS)


def test_tfidf_ranks_a_near_duplicate_above_an_unrelated_document():
    encoder = build_encoder("tfidf", dim=4)
    encoder.fit(CORPUS)
    vectors = encoder.encode(CORPUS)
    query = encoder.encode(["government announced a scheme for farmers"])
    scores = (query @ vectors.T)[0]
    assert int(scores.argmax()) == 0


def test_word2vec_encoder_reports_a_missing_model_clearly():
    encoder = build_encoder("word2vec", path="does/not/exist.kv")
    with pytest.raises(RuntimeError, match="train_word2vec"):
        encoder.encode(CORPUS)


# -----------------------------------------------------------------------------
# DenseRetriever
# -----------------------------------------------------------------------------


def _write_index(tmp_path: Path, vectors: np.ndarray, ids: list[str]) -> Path:
    import json

    np.save(tmp_path / "fake.npy", vectors.astype(np.float16))
    (tmp_path / "ids.json").write_text(json.dumps({"n": len(ids), "ids": ids}),
                                       encoding="utf-8")
    return tmp_path


class _FixedEncoder:
    """Returns a preset matrix, so ranking is tested without any model."""

    def __init__(self, matrix):
        self.matrix = matrix

    def fit(self, corpus):
        pass

    def encode(self, texts, batch_size=32):
        return self.matrix[:len(texts)]


def test_dense_retriever_reports_a_missing_index_clearly(tmp_path):
    retriever = DenseRetriever(encoder="fake", index_dir=tmp_path)
    with pytest.raises(RuntimeError, match="build_factcheck_index"):
        retriever.topk("anything")


def test_dense_retriever_refuses_an_index_that_disagrees_with_its_ids(tmp_path):
    """Three vectors and two ids means every rank past the second is wrong.

    Silently zipping them would return confidently mislabelled documents.
    """
    _write_index(tmp_path, np.eye(3, dtype=np.float32), ["a", "b"])
    retriever = DenseRetriever(encoder="fake", index_dir=tmp_path)
    with pytest.raises(RuntimeError, match="index/ids mismatch"):
        retriever.topk("anything")


def test_dense_retriever_ranks_by_cosine_and_orders_descending(tmp_path):
    corpus = l2_normalize(np.array([
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float32))
    _write_index(tmp_path, corpus, ["doc-a", "doc-b", "doc-c", "doc-d"])

    retriever = DenseRetriever(encoder="fake", index_dir=tmp_path, k=3)
    retriever._encoder = _FixedEncoder(l2_normalize(np.array([[1.0, 0.0, 0.0]],
                                                            dtype=np.float32)))
    ranked = retriever.topk("query")
    assert [d.doc_id for d in ranked] == ["doc-a", "doc-b", "doc-c"]
    assert ranked[0].score == pytest.approx(1.0, abs=1e-3)
    assert ranked[0].score > ranked[1].score > ranked[2].score


def test_rank_batch_matches_one_call_per_query(tmp_path):
    """Batching must be a cost optimisation and nothing else."""
    rng = np.random.default_rng(42)
    corpus = l2_normalize(rng.normal(size=(20, 8)).astype(np.float32))
    _write_index(tmp_path, corpus, [f"doc-{i}" for i in range(20)])
    queries = l2_normalize(rng.normal(size=(5, 8)).astype(np.float32))

    batched = DenseRetriever(encoder="fake", index_dir=tmp_path, k=5)
    batched._encoder = _FixedEncoder(queries)
    together = batched.rank_batch(["q"] * 5)

    for i in range(5):
        single = DenseRetriever(encoder="fake", index_dir=tmp_path, k=5)
        single._encoder = _FixedEncoder(queries[i:i + 1])
        alone = single.topk("q")
        assert [d.doc_id for d in alone] == [d.doc_id for d in together[i]]


def test_k_larger_than_the_corpus_does_not_crash(tmp_path):
    corpus = l2_normalize(np.eye(3, dtype=np.float32))
    _write_index(tmp_path, corpus, ["a", "b", "c"])
    retriever = DenseRetriever(encoder="fake", index_dir=tmp_path, k=50)
    retriever._encoder = _FixedEncoder(l2_normalize(np.array([[1.0, 0.0, 0.0]],
                                                            dtype=np.float32)))
    ranked = retriever.topk("query")
    assert len(ranked) <= 3
    assert ranked[0].doc_id == "a"


@pytest.mark.gpu
def test_bge_m3_uses_cls_pooling_not_mean_pooling():
    """Using the wrong pooling understates the model the ladder expects to win."""
    from retrieval.encoders import BGEM3Encoder, HFEncoder

    cls_encoder = BGEM3Encoder()
    mean_encoder = HFEncoder("bge_m3")
    text = ["The government announced a new scheme for farmers this year"]
    assert not np.allclose(cls_encoder.encode(text), mean_encoder.encode(text))
