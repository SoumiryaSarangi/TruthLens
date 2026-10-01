"""The demo evidence corpus (`retrieval/corpus.py`) and its free-text route.

The corpus has no gold, so nothing here is a metric: these pin the behaviour --
the BM25 arithmetic, the dense side proposing what BM25 cannot see, degradation,
the MANIFEST check -- on a tiny index written by the real writer.
"""

from __future__ import annotations

import numpy as np
import pytest

from retrieval.corpus import CorpusRetriever, bm25_weights, query_vector, write_index
from retrieval.factcheck_bm25 import build_weights
from retrieval.tokenize import tokenize

DOCS = [
    {"id": "fc:1", "source": "factcheck", "lang": "en", "title": "Fact Check: no Rs 6000",
     "url": "https://fc.example/1", "text": "Government is not giving Rs 6000 to every student"},
    {"id": "wiki:hi:5", "source": "wikipedia", "lang": "hi", "title": "दिल्ली",
     "url": "https://hi.wikipedia.org/wiki/x", "text": "दिल्ली भारत की राजधानी है।"},
    {"id": "wiki:pa:9", "source": "wikipedia", "lang": "pa", "title": "ਲਾਹੌਰ",
     "url": "https://pa.wikipedia.org/wiki/y", "text": "ਲਾਹੌਰ ਪੰਜਾਬ ਦਾ ਸ਼ਹਿਰ ਹੈ।"},
    {"id": "fc:2", "source": "factcheck", "lang": "en", "title": "Lemon cures cancer? No",
     "url": "https://fc.example/2", "text": "Lemon water does not cure cancer"},
]


class ConceptEncoder:
    """Maps the romanized query "dilli rajdhani" onto the Hindi Delhi lead.

    No token is shared, so BM25 scores the Delhi lead zero; only a dense side
    that proposes its own candidates can find it -- the case this retriever's
    union exists for.
    """

    CONCEPTS = (("दिल्ली", "dilli"), ("6000", "student"), ("lemon", "cancer"), ("ਲਾਹੌਰ",))

    def encode(self, texts, batch_size=32):
        out = np.zeros((len(texts), len(self.CONCEPTS) + 1), dtype=np.float32)
        for i, text in enumerate(texts):
            low = text.lower()
            hits = [c for c, words in enumerate(self.CONCEPTS)
                    if any(w in low for w in words)]
            for c in hits:
                out[i, c] = 1.0
            if not hits:
                out[i, -1] = 1.0
        return out / np.linalg.norm(out, axis=1, keepdims=True)


class BrokenEncoder:
    def encode(self, texts, batch_size=32):
        raise RuntimeError("CUDA out of memory")


@pytest.fixture
def index(tmp_path):
    write_index(tmp_path, DOCS, ConceptEncoder().encode([d["text"] for d in DOCS]),
                encoder="bge_m3", max_length=256)
    return tmp_path


def retriever(index, encoder=None, **kw) -> CorpusRetriever:
    r = CorpusRetriever(index_dir=index, **kw)
    r._encoder = encoder or ConceptEncoder()
    return r


def test_bm25_weights_score_exactly_like_the_fact_check_bm25():
    """The scipy rewrite must be BM25Okapi's arithmetic, not an approximation."""
    corpus = [d["text"] for d in DOCS] + ["the the the student", "cancer student lemon"]
    new_w, new_v = bm25_weights(corpus)
    old_w, old_v = build_weights([tokenize(t) for t in corpus])
    for query in ("student 6000", "lemon cancer the", "दिल्ली राजधानी", "nothing"):
        tokens = tokenize(query)
        a = query_vector(tokens, new_v, new_w.shape[1])
        b = query_vector(tokens, old_v, old_w.shape[1])
        if a is None:
            assert b is None
            continue
        np.testing.assert_allclose(new_w @ a, old_w @ b, rtol=1e-5)


def test_dense_side_finds_what_bm25_cannot(index):
    r = retriever(index, depth=4, k=2)
    query = "dilli rajdhani"
    r._load()
    assert not r._bm25(query).any(), "BM25 must not see it, or this tests nothing"
    ids = [d.doc_id for d in r.topk(query)]
    assert ids[0] == "wiki:hi:5"


def test_every_result_carries_a_cosine_for_the_relevance_floor(index):
    out = retriever(index, depth=4, k=4).topk("student 6000")
    assert out[0].doc_id == "fc:1"
    assert all(d.dense_score is not None for d in out)
    assert out.note is None


def test_encoder_failure_degrades_to_bm25_and_says_so(index):
    out = retriever(index, encoder=BrokenEncoder(), depth=4, k=4).topk("lemon cancer")
    assert [d.doc_id for d in out] == ["fc:2"]          # BM25's only non-zero hit
    assert out.note == "degraded: dense->bm25 (RuntimeError)"
    assert out[0].dense_score is None


def test_a_fact_check_is_read_as_its_conclusion_never_as_its_claim(index):
    """The claim field IS the rumour. As a passage it made NLI support "lemon
    water cures cancer"; the title is the fact-checker's verdict on it."""
    r = retriever(index, depth=4, k=1)
    doc = r.topk("student 6000")[0].document
    assert (doc.url, doc.title, doc.source) == ("https://fc.example/1",
                                               "Fact Check: no Rs 6000", "factcheck")
    text, span = r.best_paragraph("q", doc)
    assert text == "Fact Check: no Rs 6000" and span == (0, len(text))
    assert "giving Rs 6000" not in text


def test_a_wikipedia_lead_is_read_whole(index):
    r = retriever(index, depth=4, k=1)
    doc = r.topk("दिल्ली राजधानी")[0].document
    assert r.best_paragraph("q", doc)[0] == DOCS[1]["text"]


def test_refuses_an_index_built_with_another_encoder(tmp_path):
    write_index(tmp_path, DOCS, np.eye(len(DOCS), dtype=np.float32),
                encoder="bge_m3", max_length=512)
    with pytest.raises(RuntimeError, match="built with"):
        retriever(tmp_path).topk("x")


def test_refuses_without_a_manifest(tmp_path):
    with pytest.raises(RuntimeError, match="no evidence corpus"):
        retriever(tmp_path).topk("x")


# -----------------------------------------------------------------------------
# The free-text route through the orchestrator
# -----------------------------------------------------------------------------


def test_free_text_reaches_the_corpus_when_one_is_configured(index):
    pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    orch = Orchestrator(PipelineConfig(
        stages={"stance": "always_neutral", "free_text_retrieval": "corpus"},
        stage_args={"free_text_retrieval": {"index_dir": str(index), "depth": 4}},
        k=2,
    ))
    orch.free_text_retriever._encoder = ConceptEncoder()
    trace = orch.verify("Government will give Rs 6000 to every student.")
    res = trace.results[0]
    assert res.path == "evidence"
    assert res.passages[0].url == "https://fc.example/1"
    assert res.passages[0].title == "Fact Check: no Rs 6000"
    assert res.passages[0].text == "Fact Check: no Rs 6000"       # not the rumour
    assert not any("no candidate pool" in (e.note or "") for e in trace.events)
    assert any(e.impl == "corpus:rrf@4" for e in trace.events)
