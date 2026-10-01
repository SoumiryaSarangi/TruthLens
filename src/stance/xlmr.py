"""XLM-R-base + LoRA stance classifier, and its claim-only twin (FR-10).

The PRD's stance MODEL (`PRD.md:77`: "BiLSTM baseline, XLM-R-base model").
Trained by `scripts/train_stance.py` on the derived `averitec_stance` set.

## What has to be true for this to be worth anything

The derived gold copies a claim's verdict onto every one of its QA answers, so
within a claim the evidence cannot change the label, and across claims the claim
alone predicts it. Measured on TF-IDF: on the 1,222 dev rows where an answer was
actually found, reading the evidence gained -0.0036 macro-F1 over the claim-only
twin. A bag of words reads no usable evidence here.

The only way a model trained on these labels can use evidence is to learn a
relation that TRANSFERS across claims -- that "Did X say Y? No, he never said
it" refutes the claim -- which is what a cross-encoder reading claim and evidence
together can represent and a bag of words cannot. `XLMRClaimOnlyStance` is
trained identically on the claim alone; the gap between the two is the measure
of whether this model reads evidence. If there is no gap, this model has learned
which claims tend to be false, and the verdict will show it.

Input order is (evidence, claim) -- premise then hypothesis -- matching
`stance.nli`, so a passage is read against the claim the same way in every stance
implementation here.

Imports are lazy; `tests/test_contracts.py` fails the build otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

from stance.nli import StanceResult

MODELS = Path("data/interim/models")
STANCES = ("Supports", "Refutes", "Neutral")
MAX_LENGTH = 256
BATCH_SIZE = 32


class StanceAdapterMissing(RuntimeError):
    """The LoRA adapter has not been trained yet."""


class XLMRStance:
    name = "stance"
    impl = "xlmr"
    claim_only = False

    def __init__(self, adapter: str | os.PathLike[str] | None = None,
                 batch_size: int = BATCH_SIZE, max_length: int = MAX_LENGTH,
                 device: str | None = None, **_: object) -> None:
        self.adapter = Path(adapter) if adapter else MODELS / f"stance_{self.impl}"
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
                raise StanceAdapterMissing(
                    f"no LoRA adapter at {self.adapter}. Run "
                    f"`python scripts/train_stance.py`."
                )
            import torch
            from peft import PeftModel
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(self.adapter)
            base = AutoModelForSequenceClassification.from_pretrained(
                "xlm-roberta-base", num_labels=len(STANCES))
            self._model = PeftModel.from_pretrained(base, self.adapter).to(
                self._device).eval()
        return self._tokenizer, self._model

    def inputs(self, claim: str, passages: list[str]) -> tuple[list[str], list[str] | None]:
        """(first, second) text lists. The claim-only twin never sees a passage."""
        if self.claim_only:
            return [claim] * len(passages), None
        return list(passages), [claim] * len(passages)

    def label(self, claim: str, passages: list[str]) -> list[StanceResult]:
        if not passages:
            return []
        import torch

        tokenizer, model = self._load()
        first, second = self.inputs(claim, passages)
        out: list[StanceResult] = []
        for start in range(0, len(first), self.batch_size):
            batch_second = None if second is None else second[start:start + self.batch_size]
            encoded = tokenizer(first[start:start + self.batch_size], batch_second,
                                truncation=True, max_length=self.max_length,
                                padding=True, return_tensors="pt").to(self._device)
            with torch.inference_mode():
                probs = torch.softmax(model(**encoded).logits.float(), dim=-1)
            for row in probs.tolist():
                dist = dict(zip(STANCES, row, strict=True))
                best = max(dist, key=dist.get)
                out.append(StanceResult(best, dist[best], dist))
        return out


class XLMRClaimOnlyStance(XLMRStance):
    """Trained and run on the claim alone. The control that says whether
    `XLMRStance` reads the evidence or only learned which claims tend to be false."""

    impl = "xlmr_claimonly"
    claim_only = True
