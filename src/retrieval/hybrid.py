"""Hybrid evidence retrieval: BM25, then BGE-M3 at passage level, fused (FR-9).

FR-9: *"retrieve top-k evidence passages with hybrid BM25 + dense scoring"*.

## Why this shape, measured before it was built

Per-claim BM25 (Phase 1) finds gold far too deep to be useful. Success@k on
AVeriTeC dev, over each claim's ~1,013-document pool:

    depth     10     50     100    200    500
    success   0.158  0.350  0.474  0.584  0.700

So the gold is usually there -- just not in the top 10 the stance model reads.
A reranker over BM25's top N can in principle lift Success@10 toward BM25's own
Success@N, and that ceiling is the thing to report beside every number here.

A second ceiling sits above it: 443 of 1,096 dev gold documents (40.4%) have NO
text -- empty scrapes upstream -- and for 114 of 500 claims every gold document
is empty. No text retriever can ever find those, so Success@10 cannot exceed
0.772 on dev whatever this module does.

## Passage-level, and the passage is the evidence

Each candidate is split into passages of about `chunk_chars` characters (1,000
~= 240 XLM-R tokens, under BGE-M3's 256-token limit), and a document's dense
score is its BEST passage (MaxP). At 256 tokens a whole-document vector sees only
the first ~1,000 characters of a 4,000-character page; MaxP sees all of it.

The best passage is also what `best_paragraph` returns, so the stance model reads
the passage the retriever actually matched -- not a separately chosen paragraph
picked by lexical overlap, which could disagree with the ranking it came from.

## Degradation (NFR-7)

If the encoder cannot load or fails, the ranking falls back to BM25's own order
and says so: the returned `Ranking` carries `degraded: dense->bm25`, which the
orchestrator writes into the trace. A load failure is remembered, so a missing
model costs one failed attempt rather than one per claim.

Imports are lazy; `tests/test_contracts.py` fails the build if any module under
`src/` imports torch at module scope.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from retrieval.bm25 import BM25Retriever, Ranking, ScoredDoc
from retrieval.dense_cache import CACHE_ROOT, CachedDoc, ChunkVectorCache, text_sha1
from retrieval.kb import CACHE_ROOT as KB_CACHE_ROOT
from retrieval.kb import Document

FUSIONS = ("rrf", "weighted", "dense")
# The in-memory passage memo only has to outlive one claim: `best_paragraph` is
# called right after `topk` for the same documents. 50,000 entries grew the
# cache-warming process ~5 MB per claim -- 550 MB by claim 110 -- on a machine
# where the train knowledge-store build was already squeezing RAM. A few claims'
# worth is all the reuse there is.
_MEMO_LIMIT = 2_000


# -----------------------------------------------------------------------------
# Pure pieces, testable with no model
# -----------------------------------------------------------------------------


def chunk_spans(doc: Document, chunk_chars: int) -> list[tuple[int, int]]:
    """Passage spans into `doc.text`, packing paragraphs up to `chunk_chars`.

    Spans are computed against `Document.text` -- all paragraphs joined by a
    single space -- so `doc.text[s:e]` is the passage by construction and the
    highlight offsets the UI receives point at the real text. A paragraph longer
    than `chunk_chars` is split at whitespace. Blank paragraphs contribute
    nothing but still advance the offsets.
    """
    spans: list[tuple[int, int]] = []
    cursor = 0
    start = end = None
    for para in doc.paragraphs:
        p_start, p_end = cursor, cursor + len(para)
        cursor = p_end + 1                               # the joining space
        if not para.strip():
            continue
        if p_end - p_start > chunk_chars:
            if start is not None:
                spans.append((start, end))
                start = end = None
            spans.extend(_split_long(doc.text, p_start, p_end, chunk_chars))
            continue
        if start is None:
            start, end = p_start, p_end
        elif p_end - start <= chunk_chars:
            end = p_end
        else:
            spans.append((start, end))
            start, end = p_start, p_end
    if start is not None:
        spans.append((start, end))
    return spans


def _split_long(text: str, start: int, end: int, size: int) -> list[tuple[int, int]]:
    """Cut one over-long paragraph at whitespace into pieces of <= `size`."""
    out, cursor = [], start
    while cursor < end:
        stop = min(cursor + size, end)
        if stop < end:
            space = text.rfind(" ", cursor, stop)
            if space > cursor:
                stop = space
        if text[cursor:stop].strip():
            out.append((cursor, stop))
        cursor = stop + 1 if stop < end and text[stop:stop + 1] == " " else stop
    return out


def rrf(rankings: list[list[str]], rrf_k: int = 60) -> dict[str, float]:
    """Reciprocal rank fusion: sum over rankings of 1 / (rrf_k + rank), rank from 1.

    Rank-based on purpose. BM25 scores are unbounded and a cosine is not, so
    adding the raw scores would let whichever has the larger range decide
    everything.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


def fuse(bm25: list[ScoredDoc], dense: dict[str, float | None], fusion: str,
         rrf_k: int = 60, alpha: float = 0.5) -> list[tuple[str, float]]:
    """Combine BM25's ranking with the dense scores; best first.

    `dense[doc_id]` is None for a document with no text, which has no passage to
    embed. It is kept, ranked on BM25 alone, rather than dropped: dropping it
    would make a retriever's recall depend on the dense side being able to see a
    document at all.
    """
    if fusion not in FUSIONS:
        raise ValueError(f"fusion {fusion!r}; expected one of {FUSIONS}")
    bm25_order = [d.doc_id for d in bm25]
    scored = {d: s for d, s in dense.items() if s is not None}
    dense_order = sorted(scored, key=lambda d: (-scored[d], d))

    if fusion == "rrf":
        fused = rrf([bm25_order, dense_order], rrf_k)
    elif fusion == "weighted":
        raw = {d.doc_id: d.score for d in bm25}
        lo, hi = min(raw.values(), default=0.0), max(raw.values(), default=0.0)
        span = (hi - lo) or 1.0
        fused = {d: alpha * scored.get(d, 0.0) + (1 - alpha) * (raw[d] - lo) / span
                 for d in bm25_order}
    else:  # dense
        # Documents with no text go last, in BM25's order: a negative offset
        # keeps them below every real cosine without inventing a similarity.
        fused = {d: scored.get(d, -2.0 - i / (len(bm25_order) + 1))
                 for i, d in enumerate(bm25_order)}
    return sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))


# -----------------------------------------------------------------------------
# The retriever
# -----------------------------------------------------------------------------


class HybridRetriever:
    """BM25 over a claim's pool, then BGE-M3 passage reranking, fused."""

    name = "retrieval"

    def __init__(self, split: str = "dev", k: int = 10, depth: int = 200,
                 fusion: str = "rrf", rrf_k: int = 60, alpha: float = 0.5,
                 encoder: str = "bge_m3", max_length: int = 256,
                 chunk_chars: int = 1000, batch_size: int = 64,
                 cache: str = "readwrite", cache_root: str | Path = CACHE_ROOT,
                 **_: object) -> None:
        if fusion not in FUSIONS:
            raise ValueError(f"fusion {fusion!r}; expected one of {FUSIONS}")
        if depth < k:
            raise ValueError(f"depth {depth} is shallower than k {k}: the reranker "
                             "could never fill the list it is asked for")
        self.split, self.k, self.depth = split, k, depth
        self.fusion, self.rrf_k, self.alpha = fusion, rrf_k, alpha
        self.encoder_name, self.max_length = encoder, max_length
        self.chunk_chars, self.batch_size = chunk_chars, batch_size
        self.impl = f"hybrid:{fusion}@{depth}"
        self._bm25 = BM25Retriever(split=split, k=depth)
        self._cache = ChunkVectorCache(
            kb_split=split, encoder=encoder, max_length=max_length,
            chunk_chars=chunk_chars, max_doc_chars=_kb_max_doc_chars(split),
            root=cache_root, mode=cache,
        )
        self._encoder = None
        self._encoder_error: Exception | None = None
        # Pure caches: values are deterministic, so a race between API threads
        # costs a recomputation at worst, never a wrong answer.
        self._query_memo: dict[str, np.ndarray] = {}
        self._chunk_memo: dict[tuple[str, str], CachedDoc] = {}

    # Tests and the orchestrator's fixtures swap the knowledge store in place.
    @property
    def store(self):
        return self._bm25.store

    @store.setter
    def store(self, value) -> None:
        self._bm25.store = value

    # -- encoding -----------------------------------------------------------------
    def _get_encoder(self):
        if self._encoder_error is not None:
            raise self._encoder_error
        if self._encoder is None:
            try:
                from retrieval.encoders import build_encoder
                self._encoder = build_encoder(self.encoder_name,
                                              max_length=self.max_length)
            except Exception as exc:
                self._encoder_error = exc
                raise
        return self._encoder

    def _encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._get_encoder().encode(texts, batch_size=self.batch_size),
                          dtype=np.float32)

    def _query_vec(self, text: str) -> np.ndarray:
        vec = self._query_memo.get(text)
        if vec is None:
            vec = self._encode([text])[0]
            if len(self._query_memo) > 1000:
                self._query_memo.clear()
            self._query_memo[text] = vec
        return vec

    def _doc_chunks(self, claim_idx: int | None,
                    docs: list[Document]) -> tuple[dict[str, CachedDoc], int]:
        """Passage vectors for each document: memo, then disk, then encode.

        Returns the vectors and how many passages had to be encoded.
        """
        cached = self._cache.load(claim_idx) if claim_idx is not None else {}
        out: dict[str, CachedDoc] = {}
        fresh: dict[str, CachedDoc] = {}
        todo: list[tuple[Document, str, list[tuple[int, int]]]] = []
        for doc in docs:
            sha = text_sha1(doc.text)
            hit = self._chunk_memo.get((doc.doc_id, sha))
            if hit is None:
                on_disk = cached.get(doc.doc_id)
                if on_disk is not None and on_disk.text_sha1 == sha:
                    hit = on_disk
            if hit is not None:
                out[doc.doc_id] = hit
                continue
            spans = chunk_spans(doc, self.chunk_chars)
            if not spans:
                entry = CachedDoc(sha, np.zeros((0, 2), dtype=np.int32),
                                  np.zeros((0, 0), dtype=np.float16))
                out[doc.doc_id] = fresh[doc.doc_id] = entry
                continue
            todo.append((doc, sha, spans))

        encoded = 0
        if todo:
            texts = [doc.text[s:e] for doc, _, spans in todo for s, e in spans]
            vectors = self._encode(texts).astype(np.float16)
            encoded = len(texts)
            cursor = 0
            for doc, sha, spans in todo:
                n = len(spans)
                entry = CachedDoc(sha, np.asarray(spans, dtype=np.int32),
                                  vectors[cursor:cursor + n])
                cursor += n
                out[doc.doc_id] = fresh[doc.doc_id] = entry

        if len(self._chunk_memo) > _MEMO_LIMIT:
            self._chunk_memo.clear()
        for doc in docs:
            self._chunk_memo[(doc.doc_id, out[doc.doc_id].text_sha1)] = out[doc.doc_id]
        if claim_idx is not None:
            self._cache.save(claim_idx, fresh)
        return out, encoded

    # -- the stage ----------------------------------------------------------------
    def topk(self, claim_text: str, claim_idx: int, k: int | None = None) -> Ranking:
        k = k or self.k
        # Outside the try: a missing pool is not a dense failure, and the
        # orchestrator already turns it into NEI with a note of its own.
        cands = self._bm25.topk(claim_text, claim_idx, self.depth)
        if not cands:
            return Ranking()
        try:
            query = self._query_vec(claim_text)
            chunks, _ = self._doc_chunks(claim_idx, [c.document for c in cands])
            dense = {doc_id: (float(np.max(entry.vectors.astype(np.float32) @ query))
                              if len(entry.vectors) else None)
                     for doc_id, entry in chunks.items()}
        except Exception as exc:
            out = Ranking(cands[:k])
            out.note = f"degraded: dense->bm25 ({type(exc).__name__})"
            return out

        by_id = {c.doc_id: c for c in cands}
        return Ranking(
            ScoredDoc(doc_id, float(score), by_id[doc_id].document,
                      dense_score=dense.get(doc_id))
            for doc_id, score in fuse(cands, dense, self.fusion, self.rrf_k,
                                      self.alpha)[:k]
        )

    def best_paragraph(self, claim_text: str, doc: Document) -> tuple[str, tuple[int, int]]:
        """The passage that earned the document its dense score (MaxP)."""
        if self._encoder_error is not None:
            from retrieval.passages import best_paragraph
            return best_paragraph(claim_text, doc.paragraphs)
        chunks, _ = self._doc_chunks(None, [doc])
        entry = chunks[doc.doc_id]
        if not len(entry.spans):
            return "", (0, 0)
        best = int(np.argmax(entry.vectors.astype(np.float32) @ self._query_vec(claim_text)))
        start, end = (int(x) for x in entry.spans[best])
        return doc.text[start:end], (start, end)

    def warm(self, claim_text: str, claim_idx: int) -> int:
        """Encode and cache BM25's top `depth` for one claim; passages encoded."""
        cands = self._bm25.topk(claim_text, claim_idx, self.depth)
        _, encoded = self._doc_chunks(claim_idx, [c.document for c in cands])
        return encoded


def _kb_max_doc_chars(split: str) -> int | None:
    """The truncation the knowledge-store cache was built with, if recorded.

    Part of the vector cache's key: passages cut from 4,000-character documents
    are not the same passages as from 8,000-character ones.
    """
    path = KB_CACHE_ROOT / f"averitec_kb_{split}" / "MANIFEST.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8")).get("max_doc_chars")
    return None
