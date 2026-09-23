"""Language identification (FR-3).

fastText `lid.176` over 176 languages, narrowed to the four values the pipeline
understands: `en`, `hi`, `pa`, and `other` for everything else.

Script does most of the work and costs nothing: Devanagari is Hindi here and
Gurmukhi is Punjabi, so those rows never reach the model at all. What the model
is actually for is the hard case -- Latin script, where English, romanized Hindi
and romanized Punjabi all look the same to a script detector. That case is the
primary use case of this whole project, and it is also where `lid.176` is
weakest, because it was trained on native-script web text. Measuring that gap
honestly is the point of FR-3, so nothing here tries to hide it.

The model file is 131 MB and loads lazily, so importing this module costs
nothing and CI (which has no model and no torch) keeps working.
"""

from __future__ import annotations

import os
from pathlib import Path

from data.script_id import MIN_SCRIPT_CHARS, detect_script, script_counts

MODEL_PATH = Path("data/raw/fasttext/lid.176.bin")

# Script -> language, for the scripts that only one of our languages uses.
# Not a guess: Devanagari and Gurmukhi are unambiguous within {en, hi, pa}.
SCRIPT_LANG = {"deva": "hi", "guru": "pa"}

SUPPORTED = ("en", "hi", "pa")

# Below this, the prediction is too weak to act on and the input is reported as
# `other`. Deliberately low: `other` means "we refuse to answer" (FR-3), so a
# trigger-happy threshold turns a usable answer into a dead end. Tuned on dev,
# never on test.
DEFAULT_FLOOR = 0.30


class ModelUnavailable(RuntimeError):
    """The lid.176 binary is not on disk."""


class FastTextLID:
    """`lid.176` with a script shortcut in front of it."""

    name = "lid"
    impl = "fasttext"

    def __init__(self, model_path: str | os.PathLike[str] | None = None,
                 floor: float = DEFAULT_FLOOR) -> None:
        self.model_path = Path(model_path) if model_path else MODEL_PATH
        self.floor = floor
        self._model = None

    @property
    def available(self) -> bool:
        return self.model_path.is_file()

    def _load(self):
        if self._model is None:
            if not self.available:
                raise ModelUnavailable(
                    f"{self.model_path} not found. Run "
                    f"`python scripts/download_models.py --only fasttext`."
                )
            import fasttext

            # fastText prints a C++ deprecation banner to stderr on every load.
            fasttext.FastText.eprint = lambda *_args, **_kwargs: None
            self._model = fasttext.load_model(str(self.model_path))
        return self._model

    def identify(self, text: str) -> tuple[str, float]:
        """Return `(lang, confidence)`.

        Confidence is 1.0 for a script-decided answer, because Gurmukhi really
        is Punjabi -- that is a fact about the alphabet, not a model output.
        """
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return "other", 0.0

        script = detect_script(cleaned)
        if script in SCRIPT_LANG:
            return SCRIPT_LANG[script], 1.0

        # Too few script-bearing characters to judge: a row of digits, emoji or
        # punctuation. detect_script defaults to `latn` there, which would
        # otherwise send noise to the model and get a confident wrong answer.
        if sum(script_counts(cleaned).values()) < MIN_SCRIPT_CHARS:
            return "other", 0.0

        predictions = self._predict(cleaned.replace("\n", " "))
        if not predictions:
            return "other", 0.0

        # The TOP prediction, not the best-ranked supported one. Scanning the
        # top-k for a language we happen to support turns a confident French
        # message into English the moment `en` appears anywhere in the list.
        score, label = predictions[0]
        code = label.removeprefix("__label__")
        if code in SUPPORTED and score >= self.floor:
            return code, float(score)
        return "other", float(score)

    def _predict(self, text: str) -> list[tuple[float, str]]:
        """`[(probability, label)]`, highest first.

        Calls the C++ predictor directly rather than `model.predict`. The Python
        wrapper in fasttext-wheel 0.9.2 ends with `np.array(probs, copy=False)`,
        which NumPy 2 raises on instead of silently copying -- so every call
        through the documented API is an exception on this machine. Going one
        level down is the smaller evil: the alternative is pinning NumPy back
        for the whole project because of one wrapper line.
        """
        return self._load().f.predict(text, 5, 0.0, "strict")
