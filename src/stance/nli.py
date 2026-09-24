"""Stance via a multilingual NLI model. SYSTEM_DESIGN.md §10.

mDeBERTa-v3-base-xnli, ~0.6 GB in fp16. Off-the-shelf, not fine-tuned -- the
trained stance detector is Phase 5, and this is the baseline it has to beat.

The mapping from NLI to stance, which is the whole of the modelling here:

    entailment    -> Supports     the passage implies the claim
    contradiction -> Refutes      the passage implies the claim is false
    neutral       -> Neutral      the passage is about something else

Premise is the evidence passage and hypothesis is the claim, not the other way
round. Reversed, the model would be asked whether the claim implies the
evidence, which is a different question with a different answer.

torch and transformers are imported inside methods so that importing this
module -- which the registry does at collection time -- stays free on a machine
without them. CI depends on that.
"""

from __future__ import annotations

from dataclasses import dataclass

MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"

# The model's own label order, read from its config at load time rather than
# assumed -- getting this backwards silently inverts every verdict.
NLI_TO_STANCE = {
    "entailment": "Supports",
    "contradiction": "Refutes",
    "neutral": "Neutral",
}


@dataclass
class StanceResult:
    stance: str
    prob: float
    probs: dict[str, float]


class NLIStance:
    name = "stance"
    impl = "nli"

    def __init__(self, model_id: str = MODEL_ID, batch_size: int = 16,
                 max_length: int = 512, device: str | None = None, **_: object):
        self.model_id = model_id
        self.batch_size = batch_size
        self.max_length = max_length
        self._device = device
        self._model = None
        self._tokenizer = None
        self._id2stance: dict[int, str] = {}

    def load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_id)
        if self._device == "cuda":
            model = model.half()
        self._model = model.to(self._device).eval()

        # Build the id->stance map from the model's own config.
        for idx, label in self._model.config.id2label.items():
            key = str(label).lower()
            if key not in NLI_TO_STANCE:
                raise ValueError(
                    f"{self.model_id} has NLI label {label!r}, which is not one of "
                    f"{sorted(NLI_TO_STANCE)}. Check the mapping before trusting any verdict."
                )
            self._id2stance[int(idx)] = NLI_TO_STANCE[key]

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[StanceResult]:
        """Stance for arbitrary (premise, hypothesis) pairs, batched across all of them.

        The general primitive. `label` is one claim against many passages, which
        is the shape the evidence path needs, but the claim-matching reranker
        (FR-8) scores a different hypothesis per pair -- and forcing that through
        `label` capped the batch at one post's candidate list, ten rows instead
        of `batch_size`. Same model, same label map, one shape that serves both.
        """
        if not pairs:
            return []
        import torch

        self.load()
        out: list[StanceResult] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start : start + self.batch_size]
            enc = self._tokenizer(
                [premise for premise, _ in batch],
                [hypothesis for _, hypothesis in batch],
                truncation=True, max_length=self.max_length,
                padding=True, return_tensors="pt",
            ).to(self._device)
            with torch.no_grad():
                logits = self._model(**enc).logits.float()
            for row in torch.softmax(logits, dim=-1):
                probs = {self._id2stance[i]: float(p) for i, p in enumerate(row)}
                best = max(probs, key=probs.get)
                out.append(StanceResult(best, probs[best], probs))
        return out

    def label(self, claim: str, passages: list[str]) -> list[StanceResult]:
        """Stance of each passage toward the claim.

        premise=passage, hypothesis=claim. Reversed, the model would be asked
        whether the claim implies the evidence, which is a different question
        with a different answer.
        """
        return self.score_pairs([(passage, claim) for passage in passages])
