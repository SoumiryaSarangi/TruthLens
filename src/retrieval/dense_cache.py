"""On-disk cache of passage vectors for the hybrid retriever (FR-9).

Encode once, ablate for free. The hybrid retriever reranks BM25's top N with
BGE-M3 at passage level, and the Phase 5 ablation wants N in {100, 200, 500} and
three fusion rules. Encoding separately for each would multiply GPU time by the
number of arms; keying the cache by DOCUMENT means one pass at the deepest N makes
every shallower depth and every fusion variant a pure read.

Measured cost, on real knowledge-store documents: BGE-M3 at 256 tokens runs 103
docs/s, so N=500 over the 500 dev claims is ~2 hours at ~3 passages per document,
and each later arm is seconds.

## Layout

    data/interim/dense_cache/<key>/
        MANIFEST.json           encoder, pooling, max_length, chunk_chars, store
        {claim_idx}.npz         doc_ids, doc_sha1, offsets, spans, vectors

One file per claim, so a build is resumable and an interrupted one loses at most
the claim in flight. Vectors are fp16 -- storage, not maths; similarities are
computed in fp32 by the caller.

## When it refuses

A cache built with a different encoder, pooling, passage length or document
truncation holds vectors that are not comparable with the query's, and scoring
against them would produce a plausible ranking that means nothing. The manifest
is checked on open and a mismatch refuses. A document whose text has changed
since it was cached is re-encoded rather than trusted: the key includes a hash
of the text.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CACHE_ROOT = Path("data/interim/dense_cache")


def text_sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass
class CachedDoc:
    """One document's passages: spans into `Document.text`, and their vectors."""

    text_sha1: str
    spans: np.ndarray          # int32 (n, 2), character offsets into doc.text
    vectors: np.ndarray        # float16 (n, dim), L2-normalised


class CacheMismatch(RuntimeError):
    """The cache on disk was built with settings that do not match this run."""


class ChunkVectorCache:
    """Per-claim passage vectors, keyed by document id and text hash."""

    def __init__(self, *, kb_split: str, encoder: str, max_length: int,
                 chunk_chars: int, max_doc_chars: int | None,
                 root: Path | str = CACHE_ROOT, mode: str = "readwrite") -> None:
        if mode not in ("readwrite", "readonly", "off"):
            raise ValueError(f"cache mode {mode!r}; expected readwrite|readonly|off")
        self.mode = mode
        self.settings = {
            "kb_split": kb_split, "encoder": encoder, "pooling": "cls",
            "max_length": int(max_length), "chunk_chars": int(chunk_chars),
            "max_doc_chars": max_doc_chars,
        }
        key = (f"averitec_kb_{kb_split}__{encoder}_L{max_length}_C{chunk_chars}"
               f"_D{max_doc_chars if max_doc_chars is not None else 'na'}")
        self.dir = Path(root) / key
        self._checked = False

    # -- manifest ---------------------------------------------------------------
    def _check_manifest(self) -> None:
        if self._checked or self.mode == "off":
            return
        path = self.dir / "MANIFEST.json"
        if path.is_file():
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            differing = {k: (on_disk.get(k), v) for k, v in self.settings.items()
                         if on_disk.get(k) != v}
            if differing:
                raise CacheMismatch(
                    f"{self.dir} was built with different settings: {differing}. "
                    "Vectors from another encoder or passage length are not "
                    "comparable with this run's query vectors."
                )
        elif self.mode == "readwrite":
            self.dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        self._checked = True

    # -- per-claim load / save ----------------------------------------------------
    def load(self, claim_idx: int) -> dict[str, CachedDoc]:
        if self.mode == "off":
            return {}
        self._check_manifest()
        path = self.dir / f"{claim_idx}.npz"
        if not path.is_file():
            return {}
        with np.load(path, allow_pickle=False) as z:
            doc_ids, shas = list(z["doc_ids"]), list(z["doc_sha1"])
            offsets, spans, vectors = z["offsets"], z["spans"], z["vectors"]
        return {
            str(doc_id): CachedDoc(str(sha), spans[offsets[i]:offsets[i + 1]],
                                   vectors[offsets[i]:offsets[i + 1]])
            for i, (doc_id, sha) in enumerate(zip(doc_ids, shas, strict=True))
        }

    def save(self, claim_idx: int, docs: dict[str, CachedDoc]) -> None:
        """Merge `docs` into the claim's file and replace it atomically."""
        if self.mode != "readwrite" or not docs:
            return
        self._check_manifest()
        merged = {**self.load(claim_idx), **docs}
        doc_ids = sorted(merged)
        offsets = np.zeros(len(doc_ids) + 1, dtype=np.int64)
        for i, doc_id in enumerate(doc_ids):
            offsets[i + 1] = offsets[i] + len(merged[doc_id].spans)
        dim = next((d.vectors.shape[1] for d in merged.values() if len(d.vectors)), 0)
        # Only documents that HAVE passages contribute rows. A document with no
        # text carries a (0, 0) vector array -- its dimension was never known,
        # because nothing was encoded -- and concatenating that with (n, 1024)
        # raises. The first version did exactly that; the exception fired inside
        # the retriever's degradation handler, so every run quietly fell back to
        # BM25 and cached nothing. A test that counted encodes is what saw it.
        span_parts = [merged[d].spans for d in doc_ids if len(merged[d].spans)]
        vec_parts = [merged[d].vectors for d in doc_ids if len(merged[d].vectors)]
        spans = (np.concatenate(span_parts).astype(np.int32) if span_parts
                 else np.zeros((0, 2), dtype=np.int32))
        vectors = (np.concatenate(vec_parts).astype(np.float16) if vec_parts
                   else np.zeros((0, dim), dtype=np.float16))
        # Written to a temporary file and renamed, so an interrupted build never
        # leaves a half-written claim file that a later run would read as whole.
        tmp = self.dir / f"{claim_idx}.tmp.npz"
        np.savez(tmp, doc_ids=np.array(doc_ids), offsets=offsets,
                 doc_sha1=np.array([merged[d].text_sha1 for d in doc_ids]),
                 spans=spans, vectors=vectors)
        tmp.replace(self.dir / f"{claim_idx}.npz")
