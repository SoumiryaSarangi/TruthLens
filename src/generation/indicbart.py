"""Grounded explanations from IndicBART + LoRA (FR-15, Phase 6 decision D6).

IndicBART, not mT5 and not a prompted LLM: decided 2026-09-21 because it fits
(244M, ~0.5 GB fp16) and is an encoder-decoder, so its cross-attention is over
the actual evidence passages -- Unit IV's seq2seq-with-attention, made literal.

**Trained in English only.** AVeriTeC's ~3,000 justifications are the only
explanation gold, and they are English; Hindi and Punjabi input gets an English
explanation (cut-list item 3, recorded in the log). Every explanation was
English before this, so nothing regresses.

**Grounding is checked, not trusted.** Justifications were written against
AVeriTeC's QA pairs, so the model is trained on gold QA evidence but serves on
retrieved passages, which may not contain what it learned to say. The
orchestrator therefore never shows generated text the NLI gate has not passed
(`faithfulness/nli.py`, FR-16), and citations come from that gate -- a passage
is cited because it entails a sentence, never because the model printed `[2]`.

IndicBART's input conventions (from its model card): source `text </s> <2en>`,
target `<2en> text </s>`, the target-language tag doubling as the decoder start
token, a slow AlbertTokenizer with `keep_accents=True`. Imports are lazy.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

BASE_MODEL = "ai4bharat/IndicBART"
MODELS = Path("data/interim/models")
DEFAULT_ADAPTER = MODELS / "explainer_indicbart"
LANG_TAG = "<2en>"
MAX_SOURCE = 512
MAX_TARGET = 128
DECODING = {
    "greedy": {"num_beams": 1, "do_sample": False},
    "beam": {"num_beams": 4, "do_sample": False, "early_stopping": True},
    "nucleus": {"do_sample": True, "top_p": 0.9, "num_beams": 1},
}

# AVeriTeC annotators wrote against numbered QA pairs ("According to the QA
# pairs", "the 3rd Q&A shows"). Served, the model sees retrieved passages, and
# a sentence about "the QA pairs" is unfaithful to them by construction.
_QA_REF = re.compile(
    r"\b(?:the\s+)?(?:\d+(?:st|nd|rd|th)\s+)?"
    r"(?:QA\s*pairs?|Q\s*&\s*A(?:\s*pairs?)?s?|QAs?|questions?\s+and\s+answers?)\b",
    re.IGNORECASE)
_ACCORDING = re.compile(r"\bAccording to the evidence,?\s*", re.IGNORECASE)


# IndicBART's language tags and sentence markers are added tokens that
# `skip_special_tokens` does not remove; left in, `<2en>` and `</s>` reach the
# user and the NLI gate reads them as words.
_MARKUP = re.compile(r"<2[a-z]{2}>|</?s>|<pad>|<unk>")


def strip_markup(text: str) -> str:
    return re.sub(r"\s+", " ", _MARKUP.sub(" ", text or "")).strip()


def clean_justification(text: str) -> str:
    """A justification with its references to AVeriTeC's QA scaffolding removed."""
    out = _QA_REF.sub("the evidence", text or "")
    out = _ACCORDING.sub("", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out[:1].upper() + out[1:] if out else out


def source_text(claim: str, verdict: str, passages: Sequence[str]) -> str:
    """The encoder input, before tokenisation. Passages are numbered like the UI."""
    body = " ".join(f"[{i}] {p.strip()}" for i, p in enumerate(passages, start=1) if p)
    return f"{claim.strip()} </s> {verdict} </s> {body}"


def encode_source(tokenizer, text: str, max_length: int = MAX_SOURCE) -> list[int]:
    """Token ids ending in `</s> <2en>`, truncating the EVIDENCE, never the tags.

    Plain truncation would cut the language tag off a long input, and IndicBART
    without its tag does not know which language it is reading.
    """
    ids = tokenizer(text, add_special_tokens=False).input_ids
    tail = tokenizer(f"</s> {LANG_TAG}", add_special_tokens=False).input_ids
    return ids[:max_length - len(tail)] + tail


class IndicBARTExplainer:
    """Generation stage. Returns raw text; the orchestrator gates it (FR-16)."""

    name = "generation"
    impl = "indicbart"

    def __init__(self, adapter: str | Path | None = None, decoding: str = "beam",
                 max_new_tokens: int = MAX_TARGET, k: int = 5,
                 device: str | None = None, attn_implementation: str | None = None,
                 **_: object) -> None:
        if decoding not in DECODING:
            raise ValueError(f"decoding {decoding!r}; expected one of {sorted(DECODING)}")
        self.adapter = Path(adapter) if adapter else DEFAULT_ADAPTER
        self.decoding = decoding
        self.max_new_tokens = max_new_tokens
        self.k = k
        self._device = device
        # "eager" only for the attention figure: SDPA, the default, is faster
        # and does not return attention weights.
        self.attn_implementation = attn_implementation
        self._model = None
        self._tokenizer = None

    @property
    def available(self) -> bool:
        return (self.adapter / "adapter_config.json").is_file()

    def _load(self):
        if self._model is None:
            if not self.available:
                raise FileNotFoundError(
                    f"no explainer adapter at {self.adapter}. Train it with "
                    "`python scripts/train_explainer.py`."
                )
            import torch
            from peft import PeftModel
            from transformers import AlbertTokenizer, MBartForConditionalGeneration

            self._device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._tokenizer = AlbertTokenizer.from_pretrained(
                BASE_MODEL, do_lower_case=False, use_fast=False, keep_accents=True)
            kwargs = ({"attn_implementation": self.attn_implementation}
                      if self.attn_implementation else {})
            base = MBartForConditionalGeneration.from_pretrained(BASE_MODEL, **kwargs)
            model = PeftModel.from_pretrained(base, self.adapter)
            if self._device == "cuda" and torch.cuda.is_bf16_supported():
                # bf16, never fp16: mBART-family models overflow fp16 (the first
                # training run went to NaN loss under fp16 autocast).
                model = model.to(torch.bfloat16)
            self._model = model.to(self._device).eval()
        return self._tokenizer, self._model

    def generate(self, claim: str, verdict: str, passages: Sequence[str],
                 decoding: str | None = None, seed: int = 42) -> str:
        import torch

        tok, model = self._load()
        ids = encode_source(tok, source_text(claim, verdict, list(passages)[:self.k]))
        special = tok._convert_token_to_id_with_added_voc
        if (decoding or self.decoding) == "nucleus":
            torch.manual_seed(seed)                # sampled, so seeded per call
        with torch.inference_mode():
            out = model.generate(
                input_ids=torch.tensor([ids], device=self._device),
                max_new_tokens=self.max_new_tokens, use_cache=True,
                pad_token_id=special("<pad>"), bos_token_id=special("<s>"),
                eos_token_id=special("</s>"), decoder_start_token_id=special(LANG_TAG),
                **DECODING[decoding or self.decoding])
        text = tok.decode(out[0], skip_special_tokens=True,
                          clean_up_tokenization_spaces=False)
        return strip_markup(text)

    def explain(self, verdict: str, passages: list, *, abstained: bool = False,
                claim: str | None = None) -> tuple[str, list[str]]:
        """Raw generated text and NO citations: citations are the gate's to assign."""
        texts = [getattr(p, "text", p) for p in passages]
        return self.generate(claim or "", verdict, texts), []
