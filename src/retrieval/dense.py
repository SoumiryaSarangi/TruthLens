"""Dense retrieval over the MultiClaim fact-check pool (Phase 2 claim matching).

Different shape from `bm25.py`, and the difference is the benchmark's, not a
design preference. AVeriTeC ranks within one claim's ~1000-document pool, so
Phase 1 builds an index per claim and throws it away. MultiClaim ranks against
**one global pool of 78,077 fact-checks**, so the index is built once by
`scripts/build_factcheck_index.py` and loaded here.

The index is memory-mapped fp16 and the search is a chunked matmul. Vectors are
L2-normalised at encode time, so the inner product IS cosine similarity and
there is no scoring code here that could disagree with the encoder.

FAISS would also work and is already installed. It is not used because a flat
inner-product search over 78k x 1024 is a single matmul that numpy does in about
a second -- and every FAISS index type that is faster is also approximate, which
would put an unmeasured recall loss underneath the model comparison this ladder
exists to make.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from common.io_jsonl import load_json

INDEX_DIR = Path("data/interim/index")


@dataclass
class ScoredDoc:
    doc_id: str
    score: float
    document: object = None


class DenseRetriever:
    """Rank fact-check ids for a post. `claim_idx` is accepted and ignored.

    The signature matches `BM25Retriever.topk` so both are interchangeable
    through the registry, but there is no per-claim pool here: the pool is
    global, which is what `claim_idx` would have selected.
    """

    name = "retrieval"
    impl = "dense"

    def __init__(self, encoder: str = "bge_m3", k: int = 10,
                 index_dir: str | Path | None = None,
                 batch_size: int = 32, **_: object) -> None:
        self.encoder_name = encoder
        self.k = k
        self.batch_size = batch_size
        self.index_dir = Path(index_dir) if index_dir else INDEX_DIR
        self._matrix = None
        self._ids: list[str] = []
        self._encoder = None

    def _load(self):
        if self._matrix is None:
            matrix_path = self.index_dir / f"{self.encoder_name}.npy"
            ids_path = self.index_dir / "ids.json"
            if not matrix_path.is_file() or not ids_path.is_file():
                raise RuntimeError(
                    f"no index at {matrix_path}. Run "
                    f"`python scripts/build_factcheck_index.py --encoder "
                    f"{self.encoder_name}`."
                )
            self._matrix = np.load(matrix_path, mmap_mode="r")
            self._ids = load_json(ids_path)["ids"]
            if len(self._ids) != self._matrix.shape[0]:
                raise RuntimeError(
                    f"index/ids mismatch: {self._matrix.shape[0]} vectors but "
                    f"{len(self._ids)} ids. Rebuild the index."
                )
        return self._matrix, self._ids

    def _get_encoder(self):
        if self._encoder is None:
            from retrieval.encoders import build_encoder

            self._encoder = build_encoder(self.encoder_name)
            # TF-IDF is fitted state, not weights: the vectoriser and the SVD
            # basis ARE the vector space. Loading the exact ones the index was
            # built with is what guarantees queries and documents live in the
            # same space; refitting would only approximately reproduce it.
            if self.encoder_name == "tfidf":
                self._load_tfidf_state()
        return self._encoder

    def _load_tfidf_state(self) -> None:
        import joblib

        state_path = self.index_dir / "tfidf.state.joblib"
        if not state_path.is_file():
            raise RuntimeError(
                f"no fitted TF-IDF state at {state_path}. Rebuild with "
                "`python scripts/build_factcheck_index.py --encoder tfidf`."
            )
        state = joblib.load(state_path)
        self._encoder._vectorizer = state["vectorizer"]
        self._encoder._svd = state["svd"]

    def rank_batch(self, queries: list[str], k: int | None = None,
                   chunk: int = 512) -> list[list[ScoredDoc]]:
        """Rank every query at once.

        Batched rather than one call per row because the per-row cost of a
        transformer is dominated by launch overhead: 3,153 single-row forward
        passes take minutes, one batched pass takes seconds. The encoder and the
        index are identical either way, so this changes the cost and not the
        result.
        """
        k = k or self.k
        matrix, ids = self._load()
        encoder = self._get_encoder()
        vectors = encoder.encode(queries, batch_size=self.batch_size).astype(np.float32)

        out: list[list[ScoredDoc]] = []
        for start in range(0, len(vectors), chunk):
            block = vectors[start:start + chunk]
            # fp16 index, fp32 maths: the accumulation matters more than storage.
            scores = block @ np.asarray(matrix, dtype=np.float32).T
            top = np.argpartition(-scores, kth=min(k, scores.shape[1] - 1), axis=1)[:, :k]
            for row, candidates in enumerate(top):
                ordered = candidates[np.argsort(-scores[row, candidates])]
                out.append([ScoredDoc(ids[i], float(scores[row, i])) for i in ordered])
        return out

    def topk(self, claim_text: str, claim_idx: int | None = None,
             k: int | None = None) -> list[ScoredDoc]:
        return self.rank_batch([claim_text], k=k)[0]
