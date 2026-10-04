"""Claim -> English, for the live verdict path (post-test Phase 7, route A).

Why English: the NLI model resolves "Mumbai is the capital of Maharashtra" against
"Mumbai is the capital of India" far better in English than in Hindi or Punjabi
(probe set 2: five false claims called Supported). Translating the CLAIM, rather
than every page, costs one short generation and lets us read English Wikipedia.

NLLB-200 distilled 600M. On the CPU a claim took 6-13 s (spike), so the orchestrator
places it on the GPU in half precision (about 1.2 GiB; the stack peaks at 4.6 of
6 GiB). The model is loaded on first use, so offline requests never pay for it.

Romanized input is NOT translated as typed: NLLB has no Latin-script Hindi, so the
caller passes the native-script form (lexicon transliteration) when there is one.
Failures raise; the caller degrades to the language-matched path.
"""

from __future__ import annotations

import threading

MODEL = "facebook/nllb-200-distilled-600M"
NLLB_CODES = {"en": "eng_Latn", "hi": "hin_Deva", "pa": "pan_Guru"}
MAX_NEW_TOKENS = 64
_GPU_LOCK = threading.RLock()     # one translation on the GPU at a time


class NllbTranslator:
    def __init__(self, model: str = MODEL, device: str = "cpu") -> None:
        self.model_name = model
        self.device = device
        self._tok = None
        self._model = None
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str, str], str] = {}

    def _load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._tok = AutoTokenizer.from_pretrained(self.model_name)
            import torch

            dtype = torch.float16 if self.device == "cuda" else torch.float32
            # Kept in CPU RAM and moved to the GPU only while translating (the weights are the
            # same fp16, so the output is the same): resident it costs 1.6 GiB of a 6 GiB card.
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name, torch_dtype=dtype).eval()

    def to_english(self, text: str, lang: str) -> str:
        """English for `text` written in `lang` (native script). English passes through."""
        return self.translate(text, lang, "en")

    def translate(self, text: str, src: str, dst: str) -> str:
        """`text` from `src` to `dst` (codes in NLLB_CODES). Same language passes through."""
        if src == dst or src not in NLLB_CODES or dst not in NLLB_CODES or not text.strip():
            return text
        key = (src, dst, text)
        if key in self._cache:
            return self._cache[key]
        self._load()
        import torch

        self._tok.src_lang = NLLB_CODES[src]
        batch = self._tok(text, return_tensors="pt", truncation=True, max_length=128).to(self.device)
        with _GPU_LOCK:
            if self.device == "cuda":
                self._model.to("cuda")
            try:
                with torch.no_grad():
                    out = self._model.generate(
                        **batch, forced_bos_token_id=self._tok.convert_tokens_to_ids(NLLB_CODES[dst]),
                        max_new_tokens=MAX_NEW_TOKENS, max_length=None, num_beams=4)
            finally:
                if self.device == "cuda":
                    self._model.to("cpu")
                    torch.cuda.empty_cache()
        result = self._tok.batch_decode(out, skip_special_tokens=True)[0].strip()
        self._cache[key] = result
        return result
