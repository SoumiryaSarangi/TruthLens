"""The Phase 2 embedding ladder: one interface, five rungs.

    tfidf -> word2vec -> muril -> labse -> bge_m3

Scored on MultiClaim claim matching, which is the only multilingual retrieval
task in this project. The ladder is the Unit I/II narrative of the report and
the thing the native-vs-romanized table is measured on.

Every model import is inside a method. `tests/test_contracts.py` fails the build
if any module under `src/` imports torch, transformers, sentence_transformers or
faiss at module scope, because CI installs the core lock and has none of them.

## What each rung is for

`tfidf`      Lexical. The floor that tells you whether a neural model is
             earning its keep. It should do REASONABLY on native-script pairs
             sharing vocabulary and BADLY across scripts, because "सरकार" and
             "sarkar" share no characters at all -- which is the single clearest
             demonstration of why this project needs embeddings.

`word2vec`   Static embeddings, trained in-domain (no credible pretrained
             Punjabi Word2Vec exists and the fastText vector files are ~7 GB per
             language). One vector per word, averaged over the document, so it
             cannot represent word order or context. Handles romanized text
             natively because it is trained on it.

`muril`      Indic-focused BERT. Mean-pooled, NOT trained for retrieval -- a
             masked-LM's CLS/mean vectors are known to be weak similarity
             features, and showing that is the point of including it.

`labse`      Trained for bitext alignment: "is this the translation of that".
             Close to, but not the same as, "is this fact-check about this
             post". CLAUDE.md restricts it to the t-SNE figure for retrieval
             precisely because of this, and the ladder is where that restriction
             gets its evidence (it scored 0.188 nDCG@10 on BEIR).

`bge_m3`     Trained for multilingual retrieval. Expected to win. If it does
             not, suspect the evaluation before believing the result.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

# Each neural rung is loaded by id from the HuggingFace cache (HF_HOME, which
# docs/environment.md redirects to D:). Nothing here downloads.
HF_IDS = {
    "muril": "google/muril-base-cased",
    "labse": "sentence-transformers/LaBSE",
    "bge_m3": "BAAI/bge-m3",
}

WORD2VEC_PATH = Path("data/interim/models/word2vec.kv")


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Unit-length rows, so inner product IS cosine similarity.

    Done once at encode time rather than at search time: the corpus is encoded
    once and searched many times, and an unnormalised corpus matrix silently
    turns the ranking into "longest vector wins".
    """
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


class Encoder:
    """Text in, L2-normalised float32 matrix out."""

    name = "encoder"
    dim: int = 0

    def fit(self, corpus: list[str]) -> None:
        """Only the unsupervised rungs need this; the neural ones ignore it."""

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        raise NotImplementedError


class TfidfEncoder(Encoder):
    """Character n-gram TF-IDF.

    Character rather than word n-grams even though this is the "lexical" rung,
    because a word-level vectoriser over Devanagari, Gurmukhi and Latin at once
    is not a fair lexical baseline -- it would fail on tokenisation rather than
    on the thing being demonstrated. Characters give the strongest honest
    lexical floor, which is what a baseline should be.
    """

    name = "tfidf"

    def __init__(self, max_features: int = 200_000, dim: int = 512) -> None:
        self.max_features = max_features
        self.dim = dim
        self._vectorizer = None
        self._svd = None

    def fit(self, corpus: list[str]) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 4),
            min_df=3, max_features=self.max_features, sublinear_tf=True,
        )
        sparse = self._vectorizer.fit_transform(corpus)
        # Dense-reduced so every rung is searched by the same inner product and
        # the comparison is between representations, not between search methods.
        self._svd = TruncatedSVD(n_components=self.dim, random_state=42)
        self._svd.fit(sparse)

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if self._vectorizer is None:
            raise RuntimeError("TfidfEncoder.fit must be called before encode")
        reduced = self._svd.transform(self._vectorizer.transform(texts))
        return l2_normalize(reduced.astype(np.float32))


class Word2VecEncoder(Encoder):
    """In-domain Word2Vec, averaged over the document.

    Averaging is the standard way to get a sentence vector out of static word
    vectors and also its main weakness: it throws away word order entirely, so
    "A refutes B" and "B refutes A" encode identically. Worth seeing on the
    ladder rather than asserting.
    """

    name = "word2vec"

    def __init__(self, path: str | os.PathLike[str] | None = None, dim: int = 300) -> None:
        self.path = Path(path) if path else WORD2VEC_PATH
        self.dim = dim
        self._vectors = None

    def _load(self):
        if self._vectors is None:
            if not self.path.is_file():
                raise RuntimeError(
                    f"{self.path} not found. Run `python scripts/train_word2vec.py`."
                )
            from gensim.models import KeyedVectors

            self._vectors = KeyedVectors.load(str(self.path))
            self.dim = self._vectors.vector_size
        return self._vectors

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        vectors = self._load()
        out = np.zeros((len(texts), vectors.vector_size), dtype=np.float32)
        for i, text in enumerate(texts):
            known = [vectors[t] for t in text.lower().split() if t in vectors]
            if known:
                out[i] = np.mean(known, axis=0)
        return l2_normalize(out)


class HFEncoder(Encoder):
    """Mean-pooled transformer embeddings, fp16 on GPU when one is present."""

    def __init__(self, key: str, max_length: int = 256, device: str | None = None) -> None:
        self.key = key
        self.name = key
        self.repo_id = HF_IDS[key]
        self.max_length = max_length
        self._device = device
        self._tokenizer = None
        self._model = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import AutoModel, AutoTokenizer

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(self.repo_id)
            model = AutoModel.from_pretrained(
                self.repo_id,
                dtype=torch.float16 if self._device == "cuda" else torch.float32,
            )
            self._model = model.to(self._device).eval()
            self.dim = int(self._model.config.hidden_size)
        return self._tokenizer, self._model

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        import torch

        tokenizer, model = self._load()
        chunks: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                encoded = tokenizer(
                    batch, padding=True, truncation=True,
                    max_length=self.max_length, return_tensors="pt",
                ).to(self._device)
                hidden = model(**encoded).last_hidden_state
                # Mean pool over real tokens only. Including padding would make
                # a short document's vector depend on the longest one in its
                # batch, which is a silent, batch-order-dependent bug.
                mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                chunks.append(pooled.float().cpu().numpy())
        return l2_normalize(np.vstack(chunks))


class BGEM3Encoder(HFEncoder):
    """BGE-M3, which uses the CLS token rather than a mean pool.

    Not a detail: BGE-M3 is trained with a contrastive objective on the CLS
    position, so mean pooling it measures something the model was never
    optimised for and would understate it. Using the wrong pooling is one of the
    easier ways to accidentally conclude that the best model is the worst.
    """

    def __init__(self, max_length: int = 256, device: str | None = None) -> None:
        super().__init__("bge_m3", max_length=max_length, device=device)

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        import torch

        tokenizer, model = self._load()
        chunks: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                encoded = tokenizer(
                    batch, padding=True, truncation=True,
                    max_length=self.max_length, return_tensors="pt",
                ).to(self._device)
                cls = model(**encoded).last_hidden_state[:, 0]
                chunks.append(cls.float().cpu().numpy())
        return l2_normalize(np.vstack(chunks))


ENCODERS = {
    "tfidf": TfidfEncoder,
    "word2vec": Word2VecEncoder,
    "muril": lambda **kw: HFEncoder("muril", **kw),
    "labse": lambda **kw: HFEncoder("labse", **kw),
    "bge_m3": BGEM3Encoder,
}

# The order the report reads in: cheapest and dumbest first.
LADDER = ("tfidf", "word2vec", "muril", "labse", "bge_m3")


def build_encoder(name: str, **kwargs) -> Encoder:
    if name not in ENCODERS:
        raise ValueError(f"unknown encoder {name!r}; registered: {sorted(ENCODERS)}")
    return ENCODERS[name](**kwargs)
