"""The demo evidence corpus: one global hybrid index for free-text forwards.

`HybridRetriever` ranks within ONE AVeriTeC claim's pool, which is the
evaluation protocol and useless for a forward nobody has seen: there is no pool.
Until this module, every forward that missed the fast path answered "no
evidence corpus is available". SYSTEM_DESIGN.md §14 (decision D7) defines the
corpus this searches instead:

* Hindi and Punjabi Wikipedia **lead sections** -- entity grounding: who a
  minister is, what a scheme is.
* The **78,077 MultiClaim fact-checks** -- the fast path's own pool doubling as
  evidence, because a fact-check that is a near miss for the fast path's tau is
  still the most relevant thing this system has to read.

The AVeriTeC knowledge store is deliberately NOT in it: ~500k pages scraped for
specific US-centric claims fit Indian forwards poorly (confirmed in planning).
Evaluation never touches this module; it always uses AVeriTeC's own pools.

## Shape

Global BM25 top `depth` UNION global BGE-M3 top `depth`, fused by RRF -- the
same fusion that won the Phase 5 ablation. Unlike the per-claim retriever, the
dense side here proposes its own candidates rather than only reranking BM25's,
because there is no small pool to rerank: a romanized or paraphrased forward
can share no token with the right lead and still sit near it in BGE-M3's space.

Every document is one passage. Leads are capped at ~1,200 characters at build
time -- about what BGE-M3 sees at 256 tokens -- and fact-checks are a sentence
or two, so the passage the stance model reads is the text that was matched.

This corpus has no gold, so there is no metric for it: it is verified by smoke
test and the demo (`tests/test_corpus_retriever.py`), never by an invented
number.

## Why no FAISS

As in `dense.py`: a flat inner product over ~300k x 1024 is a blocked matmul
that numpy does in well under a second, and every faster FAISS index is
approximate.

Imports of torch are lazy, through the encoder.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from retrieval.bm25 import Ranking, ScoredDoc
from retrieval.factcheck_bm25 import EPSILON, K1, B
from retrieval.hybrid import rrf
from retrieval.kb import Document
from retrieval.tokenize import tokenize

INDEX_DIR = Path("data/interim/evidence")
FUSIONS = ("rrf", "dense", "bm25")
# Rows per block in the dense search. 32k x 1024 fp32 is 128 MB of temporary,
# where converting the whole fp16 matrix at once (as `dense.py` does for 78k
# rows) would allocate 1.2 GB per query in a server process.
_BLOCK = 32_768


@dataclass(frozen=True)
class CorpusDocument(Document):
    """A `Document` with the provenance a passage card needs.

    Subclassed rather than a new type so the lexical fallback in the
    orchestrator, which reads `paragraphs`, keeps working unchanged.

    `paragraphs` holds the PASSAGE -- what the stance model reads -- which is not
    always the text that was indexed. See `passage_text`.
    """

    url: str = ""
    title: str = ""
    source: str = ""          # "wikipedia" or "factcheck"
    lang: str = ""


def passage_text(rec: dict) -> str:
    """What the stance model reads for one corpus record.

    A fact-check is indexed by "claim + title", which is right for RETRIEVAL --
    a forward repeats the claim. It is exactly wrong as EVIDENCE: the claim
    field is the misinformation itself, stated as fact. Handed "Cancer can be
    cured using hot lemon water. Recent Facebook claims about cancer ... not
    accurate", NLI read the first sentence and returned Supports, and the served
    pipeline answered **Supported** to "lemon water cures cancer". Every
    fact-check passage was giving the stance model the rumour it debunks.

    So a fact-check's passage is its TITLE -- the fact-checker's own conclusion
    -- and never its claim. Found by running real forwards; no metric could have
    shown it, because this corpus has no gold.
    """
    if rec.get("source") == "factcheck" and rec.get("title"):
        return rec["title"]
    return rec["text"]


# -----------------------------------------------------------------------------
# BM25 weights without Python lists of postings
# -----------------------------------------------------------------------------


def bm25_weights(texts) -> tuple:
    """(csr_matrix, vocab) of BM25Okapi term weights, built through scipy.

    `factcheck_bm25.build_weights` holds one Counter per document and three
    Python lists of postings -- fine for 78k short fact-checks, ~3 GB for ~300k
    documents with leads in them. This computes the identical weights from a
    sparse count matrix instead: same IDF, same negative-IDF floor, same length
    normalisation (`tests/test_corpus_retriever.py` checks the scores agree).
    """
    from sklearn.feature_extraction.text import CountVectorizer

    vectorizer = CountVectorizer(tokenizer=tokenize, lowercase=False,
                                 token_pattern=None, dtype=np.float32)
    counts = vectorizer.fit_transform(texts).tocsr()
    n_docs = counts.shape[0]
    lengths = np.asarray(counts.sum(axis=1)).ravel().astype(np.float64)
    avgdl = lengths.mean() if n_docs else 0.0

    df = np.bincount(counts.indices, minlength=counts.shape[1]).astype(np.float64)
    idf = np.log(n_docs - df + 0.5) - np.log(df + 0.5)
    if idf.size:
        negative = idf < 0
        idf[negative] = EPSILON * float(idf.mean())

    norm = K1 * (1 - B + B * lengths / avgdl) if avgdl else np.zeros(n_docs)
    rows = np.repeat(np.arange(n_docs), np.diff(counts.indptr))
    f = counts.data.astype(np.float64)
    counts.data = (idf[counts.indices] * f * (K1 + 1) / (f + norm[rows])).astype(np.float32)
    vocab = {term: int(col) for term, col in vectorizer.vocabulary_.items()}
    return counts, vocab


def query_vector(tokens: list[str], vocab: dict[str, int], width: int) -> np.ndarray | None:
    """Term counts for one query; None if no token is in the vocabulary."""
    query = np.zeros(width, dtype=np.float32)
    hits = 0
    for term in tokens:
        col = vocab.get(term)
        if col is not None:
            query[col] += 1.0              # counted, as BM25Okapi loops the tokens
            hits += 1
    return query if hits else None


def top_n(scores: np.ndarray, n: int) -> np.ndarray:
    """Indices of the `n` best scores, best first, ties by index."""
    n = min(n, scores.shape[0])
    if n <= 0:
        return np.empty(0, dtype=np.int64)
    top = np.argpartition(-scores, kth=n - 1)[:n]
    return top[np.lexsort((top, -scores[top]))]


def write_index(out: Path, docs: list[dict], vectors: np.ndarray,
                encoder: str, max_length: int, **manifest) -> dict:
    """Write a corpus `CorpusRetriever` can load; MANIFEST last.

    The one writer for the build script and the tests, so a test index has
    exactly the layout of the real one. A write killed halfway leaves no
    MANIFEST, and the retriever refuses to load without one.
    """
    from scipy.sparse import save_npz

    if len(docs) != vectors.shape[0]:
        raise ValueError(f"{len(docs)} documents but {vectors.shape[0]} vectors")
    out.mkdir(parents=True, exist_ok=True)
    (out / "MANIFEST.json").unlink(missing_ok=True)
    weights, vocab = bm25_weights(d["text"] for d in docs)
    offsets = np.empty(len(docs), dtype=np.int64)
    with (out / "docs.jsonl").open("wb") as fh:
        for i, d in enumerate(docs):
            offsets[i] = fh.tell()
            fh.write((json.dumps(d, ensure_ascii=False) + "\n").encode("utf-8"))
    np.save(out / "offsets.npy", offsets)
    np.save(out / f"{encoder}.npy", vectors.astype(np.float16))
    save_npz(out / "bm25.npz", weights)
    (out / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False),
                                    encoding="utf-8")
    full = {"encoder": encoder, "max_length": max_length,
            "documents": len(docs), "vocab": len(vocab), **manifest}
    (out / "MANIFEST.json").write_text(json.dumps(full, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    return full


# -----------------------------------------------------------------------------
# The retriever
# -----------------------------------------------------------------------------


class CorpusRetriever:
    """Free-text evidence retrieval over the demo corpus.

    `topk(text, claim_idx)` matches `HybridRetriever.topk` so the orchestrator
    treats both the same way; `claim_idx` is accepted and ignored, because the
    pool here is global.
    """

    name = "retrieval"

    def __init__(self, k: int = 10, depth: int = 100, fusion: str = "rrf",
                 rrf_k: int = 60, index_dir: str | Path | None = None,
                 encoder: str = "bge_m3", max_length: int = 256,
                 batch_size: int = 32, **_: object) -> None:
        if fusion not in FUSIONS:
            raise ValueError(f"fusion {fusion!r}; expected one of {FUSIONS}")
        self.k, self.depth, self.fusion, self.rrf_k = k, depth, fusion, rrf_k
        self.index_dir = Path(index_dir) if index_dir else INDEX_DIR
        self.encoder_name, self.max_length = encoder, max_length
        self.batch_size = batch_size
        self.impl = f"corpus:{fusion}@{depth}"
        self._lock = threading.Lock()
        self._loaded = False
        self._encoder = None
        self._encoder_error: Exception | None = None

    # -- loading ------------------------------------------------------------
    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            from scipy.sparse import load_npz

            manifest_path = self.index_dir / "MANIFEST.json"
            if not manifest_path.is_file():
                raise RuntimeError(
                    f"no evidence corpus at {self.index_dir}. Run "
                    "`python scripts/build_evidence_index.py`."
                )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            built = (manifest.get("encoder"), manifest.get("max_length"))
            if built != (self.encoder_name, self.max_length):
                # Query vectors from a different encoder or truncation live in a
                # different space; the cosines would be meaningless, not lower.
                raise RuntimeError(
                    f"evidence corpus was built with {built}, this retriever "
                    f"encodes with {(self.encoder_name, self.max_length)}"
                )
            self._offsets = np.load(self.index_dir / "offsets.npy")
            self._weights = load_npz(self.index_dir / "bm25.npz").tocsr()
            self._vocab = json.loads((self.index_dir / "vocab.json")
                                     .read_text(encoding="utf-8"))
            self._matrix = np.load(self.index_dir / f"{self.encoder_name}.npy",
                                   mmap_mode="r")
            n = len(self._offsets)
            if self._weights.shape[0] != n or self._matrix.shape[0] != n:
                raise RuntimeError(
                    f"evidence corpus is inconsistent: {n} documents, "
                    f"{self._weights.shape[0]} BM25 rows, {self._matrix.shape[0]} "
                    "vectors. Rebuild it."
                )
            self._loaded = True

    def _get_encoder(self):
        if self._encoder_error is not None:
            raise self._encoder_error
        if self._encoder is None:
            try:
                from retrieval.encoders import shared_encoder

                self._encoder = shared_encoder(self.encoder_name,
                                               max_length=self.max_length)
            except Exception as exc:
                # Remembered: a missing model costs one failed attempt, not one
                # per request.
                self._encoder_error = exc
                raise
        return self._encoder

    def document(self, row: int) -> CorpusDocument:
        """One document, read from disk by byte offset.

        The texts are not held in memory: ~300k documents would be ~0.5 GB of
        Python strings in the API process, to serve ten per request.
        """
        with (self.index_dir / "docs.jsonl").open("rb") as fh:
            fh.seek(int(self._offsets[row]))
            rec = json.loads(fh.readline())
        return CorpusDocument(rec["id"], (passage_text(rec),), False, url=rec["url"],
                              title=rec.get("title", ""), source=rec["source"],
                              lang=rec.get("lang", ""))

    # -- scoring ------------------------------------------------------------
    def _bm25(self, text: str) -> np.ndarray:
        query = query_vector(tokenize(text), self._vocab, self._weights.shape[1])
        if query is None:
            return np.zeros(self._weights.shape[0], dtype=np.float32)
        return self._weights @ query

    def _cosines(self, vec: np.ndarray) -> np.ndarray:
        out = np.empty(self._matrix.shape[0], dtype=np.float32)
        for start in range(0, self._matrix.shape[0], _BLOCK):
            block = np.asarray(self._matrix[start:start + _BLOCK], dtype=np.float32)
            out[start:start + len(block)] = block @ vec
        return out

    def topk(self, claim_text: str, claim_idx: int | None = None,
             k: int | None = None) -> Ranking:
        self._load()
        k = k or self.k
        lexical = self._bm25(claim_text)
        bm25_rows = [int(i) for i in top_n(lexical, self.depth) if lexical[i] > 0]

        note = None
        cosines = None
        if self.fusion != "bm25":
            try:
                vec = self._get_encoder().encode([claim_text], batch_size=1)[0]
                cosines = self._cosines(vec.astype(np.float32))
            except Exception as exc:
                note = f"degraded: dense->bm25 ({type(exc).__name__})"

        if cosines is None:
            order = [(r, float(lexical[r])) for r in bm25_rows[:k]]
        else:
            dense_rows = [int(i) for i in top_n(cosines, self.depth)]
            if self.fusion == "dense":
                order = [(r, float(cosines[r])) for r in dense_rows[:k]]
            else:
                fused = rrf([[str(r) for r in bm25_rows], [str(r) for r in dense_rows]],
                            self.rrf_k)
                ranked = sorted(fused.items(), key=lambda kv: (-kv[1], int(kv[0])))
                order = [(int(r), score) for r, score in ranked[:k]]

        out = Ranking()
        for row, score in order:
            doc = self.document(row)
            out.append(ScoredDoc(
                doc.doc_id, score, doc,
                # Every document here has a vector, so the relevance floor
                # (FR-12) can read a cosine for all of them, not only the ones
                # the dense side happened to propose.
                dense_score=None if cosines is None else float(cosines[row]),
            ))
        out.note = note
        return out

    def best_paragraph(self, claim_text: str, doc: Document) -> tuple[str, tuple[int, int]]:
        """The whole passage: each document is already a single one."""
        text = doc.text
        return text, (0, len(text))
