"""Rerankers for the claim-matching fast path (FR-8).

## Why the fast path needs one at all

The bi-encoder ranks well and scores badly. Measured on Phase 2's own
predictions, before any of this existed: a CORRECT top-1 scores 0.7239 on
average and a WRONG one 0.6500, and the two distributions overlap heavily.
Turning that into a decision gives no usable operating point --

    tau 0.70  ->  40.5% of posts resolved, 62.7% of them citing the right check
    tau 0.90  ->   1.7% of posts resolved, 81.8% of them citing the right check

-- and an 18% wrong-citation rate at 1.7% coverage is not a feature that can
ship. MRR 0.5244 was never wrong; it simply answers a different question, because
rank metrics are scale-free.

A bi-encoder scores a post and a fact-check independently and compares two
vectors. A cross-encoder reads them together, which is the whole reason it can
tell "same claim" from "same topic" -- and "same topic, different claim" is
exactly what the bi-encoder's wrong top-1 looks like.

## Two arms, the Phase 3 shape repeated because it worked

    xlmr   XLM-R-base + LoRA, trained on MultiClaim train pairs with hard
           negatives mined from the bi-encoder itself
    nli    mDeBERTa-XNLI zero-shot, already on disk, trained on nothing of ours

Phase 3 ran that pairing for check-worthiness and the zero-shot arm won, which
is why the control is not optional here. A trained model that cannot beat a
model that has never seen the task has not learned the task -- it has learned
the training set.

Imports are lazy; `tests/test_contracts.py` fails the build if any module under
`src/` imports torch at module scope.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ADAPTER = Path("data/interim/models/reranker_xlmr")
MAX_LENGTH = 256
BATCH_SIZE = 64

# The hypothesis the zero-shot arm scores. Kept here rather than inline because
# a zero-shot arm IS its prompt: changing this string is changing the model.
NLI_TEMPLATE = "This message is about the same claim."


class RerankerUnavailable(RuntimeError):
    """The reranker adapter has not been trained yet."""


class NLIReranker:
    """Zero-shot: P(entailment) that the post entails the fact-check's claim.

    Premise is the POST and hypothesis is the FACT-CHECK, not the other way
    round. Reversed, the question becomes whether a fact-check article implies
    the forward, which is a different relation and is usually false even for a
    correct match -- the article is longer and says more.

    This is the control, and it is a weak-ish fit by construction: NLI asks
    whether one text entails another, not whether two texts are ABOUT the same
    claim. A post and its fact-check often paraphrase the same assertion, which
    entailment catches, but a fact-check that debunks a claim also contradicts
    the post that makes it. That ambiguity is the reason to measure rather than
    assume.
    """

    name = "reranker"
    impl = "nli"

    def __init__(self, batch_size: int = BATCH_SIZE, max_length: int = MAX_LENGTH,
                 **_: object) -> None:
        self.batch_size = batch_size
        self.max_length = max_length
        self._nli = None

    def _load(self):
        if self._nli is None:
            from stance.nli import NLIStance
            self._nli = NLIStance(batch_size=self.batch_size,
                                  max_length=self.max_length)
        return self._nli

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        """P(entailment) for each (post, fact-check text) pair.

        Batched across ALL pairs, not per post. Going through `NLIStance.label`
        capped the batch at one post's candidate list -- ten rows instead of
        `batch_size` -- which was the difference between minutes and over an hour
        on the dev split.
        """
        if not pairs:
            return []
        results = self._load().score_pairs(pairs)
        return [r.probs.get("Supports", 0.0) for r in results]

    def rerank(self, texts, candidates):
        return _rerank_with(self.score_pairs, texts, candidates)


class XLMRReranker:
    """XLM-R-base + LoRA cross-encoder, trained by scripts/train_reranker.py.

    Binary: does this fact-check address the same claim as this post. The score
    is P(relevant), which is in [0, 1] and therefore on the same scale as the
    cosine it replaces -- so a tau chosen for one is at least readable against
    the other. `task: fast_path` warns if it turns out not to be.
    """

    name = "reranker"
    impl = "xlmr"

    def __init__(self, adapter: str | os.PathLike[str] | None = None,
                 batch_size: int = BATCH_SIZE, max_length: int = MAX_LENGTH,
                 device: str | None = None, **_: object) -> None:
        self.adapter = Path(adapter) if adapter else DEFAULT_ADAPTER
        self.batch_size = batch_size
        self.max_length = max_length
        self._device = device
        self._model = None
        self._tokenizer = None

    @property
    def available(self) -> bool:
        return (self.adapter / "adapter_config.json").is_file()

    def _load(self):
        if self._model is None:
            if not self.available:
                raise RerankerUnavailable(
                    f"no LoRA adapter at {self.adapter}. Run "
                    "`python scripts/train_reranker.py`."
                )
            import torch
            from peft import PeftModel
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(self.adapter)
            base = AutoModelForSequenceClassification.from_pretrained(
                "xlm-roberta-base", num_labels=2,
            )
            self._model = PeftModel.from_pretrained(base, self.adapter).to(
                self._device).eval()
        return self._tokenizer, self._model

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        import torch

        tokenizer, model = self._load()
        out: list[float] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start:start + self.batch_size]
            encoded = tokenizer([p for p, _ in batch], [c for _, c in batch],
                                truncation=True, max_length=self.max_length,
                                padding=True, return_tensors="pt").to(self._device)
            with torch.inference_mode():
                logits = model(**encoded).logits.float()
            out.extend(torch.softmax(logits, dim=-1)[:, 1].tolist())
        return out

    def rerank(self, texts, candidates):
        return _rerank_with(self.score_pairs, texts, candidates)


def _rerank_with(score_pairs, texts: list[str],
                 candidates: list[list[tuple[str, str]]]) -> list[list[tuple[str, float]]]:
    """Flatten, score once, regroup, sort best-first.

    One batched call rather than one per query: a transformer's per-row cost is
    mostly launch overhead, and Phase 2 measured the difference between those two
    shapes in minutes.

    Ties are broken by doc_id so a run is reproducible -- a reranker that assigns
    two candidates the same probability is common, and a tie resolved by input
    order would resolve by the retriever's ranking without saying so.
    """
    flat: list[tuple[str, str]] = []
    for text, cands in zip(texts, candidates, strict=True):
        flat.extend((text, candidate_text) for _, candidate_text in cands)
    scores = score_pairs(flat)

    out: list[list[tuple[str, float]]] = []
    cursor = 0
    for cands in candidates:
        chunk = [(doc_id, float(scores[cursor + i]))
                 for i, (doc_id, _) in enumerate(cands)]
        cursor += len(cands)
        out.append(sorted(chunk, key=lambda pair: (-pair[1], pair[0])))
    return out


REGISTRY = {"nli": NLIReranker, "xlmr": XLMRReranker}


def build(impl: str, **kwargs):
    try:
        cls = REGISTRY[impl]
    except KeyError:
        raise ValueError(
            f"unknown reranker {impl!r}. Registered: {sorted(REGISTRY)}"
        ) from None
    return cls(**kwargs)
