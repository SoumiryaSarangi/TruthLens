"""Claim extraction with the fine-tuned XLM-R span model (FR-6, FR-7).

Two adapters, three jobs:

    span            token classification into B-CLAIM / I-CLAIM / O
    check-worthy    a SEPARATE sequence classifier (scripts/train_checkworthy.py)
    normalize       the extracted span, artefact-stripped

Check-worthiness was first derived from the span model -- if it finds no claim
token, there is no claim -- and that failed for a structural reason worth
recording. Measured on the 100 hand-typed forwards it rejected **0 of 15**
no-claim messages while getting 70/70 of the straightforward positives right.
The span model trains on X-CLAIM, where every post contains a claim, so it has
never seen the negative class and has no way to answer in the negative. No
amount of thresholding fixes a class the model was never shown.

So check-worthiness is its own classifier, trained on the derived `xclaim_cw`
set. The span-derived path survives as a fallback for when that adapter is
missing, and is documented as the bad option it is.

That classifier is not the best arm either, and the reason is the same one:
it reaches 0.7222 macro-F1 on the derived dev set and 0.4536 on the hand-typed
100, catching **0 of 15** real negatives, because `xclaim_cw`'s negatives are
out-of-span remainders that read as truncated mid-thought. `claims/nli_zeroshot.py`
-- no training at all -- catches 7 of 15 and is the arm that beats the majority
baseline. Keep this one for the derived-set comparison; do not reach for it as
the served implementation without re-reading that entry in the project log.

Normalization is EXTRACTIVE in Phase 3: the claim is the span, cleaned. It
cannot reorder, resolve a pronoun to a name, or supply a subject the post left
implicit, so it should lose to an abstractive model on chrF -- quantifying that
gap is what makes the Phase 6 upgrade justified rather than assumed.

Imports are lazy throughout. `tests/test_contracts.py` fails the build if any
module under `src/` imports torch or transformers at module scope, because CI
installs the core lock and has neither.
"""

from __future__ import annotations

import os
from pathlib import Path

from data.labels import CHECKWORTHY_BINARY, SPAN_BIO
from pipeline.contracts import MAX_CLAIMS, Claim, Trace
from preprocess.clean import strip_artefacts

DEFAULT_ADAPTER = Path("data/interim/models/span_xlmr_joint")
DEFAULT_CW_ADAPTER = Path("data/interim/models/checkworthy_xlmr")
MAX_LENGTH = 256

OUTSIDE = SPAN_BIO[2]   # "O"
CHECKWORTHY = CHECKWORTHY_BINARY   # ("Yes", "No"), and the label id order matches


class AdapterUnavailable(RuntimeError):
    """The LoRA adapter has not been trained yet."""


class SpanXLMRClaims:
    """Fine-tuned XLM-R + LoRA. Loads the adapter lazily, once."""

    name = "claims"
    impl = "xlmr"

    def __init__(self, adapter: str | os.PathLike[str] | None = None,
                 cw_adapter: str | os.PathLike[str] | None = None,
                 max_length: int = MAX_LENGTH, device: str | None = None) -> None:
        self.adapter = Path(adapter) if adapter else DEFAULT_ADAPTER
        self.cw_adapter = Path(cw_adapter) if cw_adapter else DEFAULT_CW_ADAPTER
        self.max_length = max_length
        self._device = device
        self._model = None
        self._tokenizer = None
        self._cw_model = None
        self._cw_tokenizer = None

    @property
    def available(self) -> bool:
        return (self.adapter / "adapter_config.json").is_file()

    def _load(self):
        if self._model is None:
            if not self.available:
                raise AdapterUnavailable(
                    f"no LoRA adapter at {self.adapter}. Run "
                    f"`python scripts/train_span.py --arm joint`."
                )
            import torch
            from peft import PeftModel
            from transformers import (
                AutoModelForTokenClassification,
                AutoTokenizer,
            )

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(self.adapter)
            base = AutoModelForTokenClassification.from_pretrained(
                "xlm-roberta-base", num_labels=len(SPAN_BIO),
            )
            model = PeftModel.from_pretrained(base, self.adapter)
            self._model = model.to(self._device).eval()
        return self._tokenizer, self._model

    def tag(self, tokens: list[str]) -> list[str]:
        """One BIO tag per input token.

        Tags are emitted per WORD, not per subword: the label of a word is the
        label its first subword received, which is the same convention training
        used. Words past `max_length` are truncated by the tokenizer and get `O`,
        so the returned list always matches the input length -- the harness
        refuses a prediction whose length disagrees with the gold, and a silently
        short list would be a far worse failure than a run of `O`.
        """
        import torch

        tokenizer, model = self._load()
        if not tokens:
            return []
        encoded = tokenizer([tokens], is_split_into_words=True, truncation=True,
                            max_length=self.max_length, return_tensors="pt")
        word_ids = encoded.word_ids(batch_index=0)
        with torch.inference_mode():
            logits = model(**{k: v.to(self._device) for k, v in encoded.items()}).logits
        predicted = logits.argmax(-1)[0].tolist()

        tags = [OUTSIDE] * len(tokens)
        seen: set[int] = set()
        for position, word_id in enumerate(word_ids):
            if word_id is None or word_id in seen:
                continue
            seen.add(word_id)
            if word_id < len(tags):
                tags[word_id] = SPAN_BIO[predicted[position]]
        return tags

    @staticmethod
    def spans_from_tags(tokens: list[str], tags: list[str]) -> list[tuple[int, int]]:
        """Contiguous runs of non-`O` tags, as inclusive token index pairs.

        A run is broken by `O` or by a fresh `B-CLAIM`, so two adjacent claims
        stay two claims. Runs are returned in order of appearance.
        """
        spans: list[tuple[int, int]] = []
        start: int | None = None
        for i, tag in enumerate(tags):
            if tag == OUTSIDE:
                if start is not None:
                    spans.append((start, i - 1))
                    start = None
            elif tag == SPAN_BIO[0] and start is not None:      # a new B ends the last
                spans.append((start, i - 1))
                start = i
            elif start is None:
                start = i
        if start is not None:
            spans.append((start, len(tags) - 1))
        return spans

    def _load_cw(self):
        """The dedicated check-worthiness classifier, if one has been trained."""
        if self._cw_model is None:
            import torch
            from peft import PeftModel
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._cw_tokenizer = AutoTokenizer.from_pretrained(self.cw_adapter)
            base = AutoModelForSequenceClassification.from_pretrained(
                "xlm-roberta-base", num_labels=2,
            )
            model = PeftModel.from_pretrained(base, self.cw_adapter)
            self._cw_model = model.to(self._device).eval()
        return self._cw_tokenizer, self._cw_model

    @property
    def cw_available(self) -> bool:
        return (self.cw_adapter / "adapter_config.json").is_file()

    def check_worthy(self, trace: Trace) -> bool:
        """The dedicated classifier if it exists; otherwise the span signal.

        The fallback is documented as a fallback because it is a bad one, and it
        is measured: deriving check-worthiness from "did the span model find any
        claim token" rejected 0 of 15 no-claim messages on the hand-typed set.
        The reason is structural rather than fixable by tuning -- the span model
        trains on X-CLAIM, where every post contains a claim, so it has never
        seen the negative class and cannot answer in the negative.
        """
        if not trace.pre or not trace.pre.normalized.strip():
            return False
        text = trace.pre.normalized

        if self.cw_available:
            import torch

            tokenizer, model = self._load_cw()
            encoded = tokenizer([text], truncation=True, max_length=self.max_length,
                                return_tensors="pt")
            with torch.inference_mode():
                logits = model(**{k: v.to(self._device)
                                  for k, v in encoded.items()}).logits
            return CHECKWORTHY[int(logits.argmax(-1)[0])] == "Yes"

        return any(tag != OUTSIDE for tag in self.tag(text.split()))

    def extract(self, trace: Trace) -> Trace:
        """Longest spans first, capped at MAX_CLAIMS; the rest are listed."""
        assert trace.pre is not None
        text = trace.pre.normalized
        tokens = text.split()
        tags = self.tag(tokens)
        spans = self.spans_from_tags(tokens, tags)

        candidates = [" ".join(tokens[s:e + 1]) for s, e in spans]      # inclusive
        candidates = [strip_artefacts(c) for c in candidates]
        candidates = [c for c in candidates if c]
        if not candidates:
            candidates = [text]
        ranked = sorted(candidates, key=len, reverse=True)

        trace.claims = [
            Claim(claim_id=f"c{i}", text=c, span=_locate(text, c))
            for i, c in enumerate(ranked[:MAX_CLAIMS], start=1)
        ]
        trace.unchecked_claims = ranked[MAX_CLAIMS:]
        return trace


def _locate(haystack: str, needle: str) -> tuple[int, int] | None:
    """Character offsets, per the `Claim.span` contract in SYSTEM_DESIGN 4."""
    start = haystack.find(needle)
    return (start, start + len(needle)) if start >= 0 else None
