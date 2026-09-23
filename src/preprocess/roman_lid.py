"""Language ID for LATIN-SCRIPT Hindi, Punjabi and English (FR-3).

fastText `lid.176` cannot do this. Measured, not assumed: 0 of 100 correct on
the hand-typed forwards and 0.3158 on MultiClaim's naturally romanized Hindi.
It was trained on native-script web text, so romanized Indic is simply outside
the space it models -- it answers `en`, or a random European language, or
nothing above threshold.

This is a character n-gram classifier, which is the right shape for the problem
for a reason worth stating: romanized Hindi and Punjabi are not distinguishable
by vocabulary (both borrow heavily from English, and forwards code-mix
constantly) but they ARE distinguishable by spelling habits and grammatical
endings -- Punjabi's `-nde`, `-diyan`, `nu`, `te`, `aa` against Hindi's `-ta
hai`, `-ne`, `ko`, `mein`. Those are 3-to-5 character patterns. A word-level
model would miss them; a character model finds them without being told.

## Training data, and why it is honest

TRAIN SPLITS ONLY, plus Dakshina. The hand-typed forwards are `dev` and are
never opened by the trainer, so the FR-3 number on them stays a real held-out
measurement -- checked directly, not assumed: none of the 100 appears verbatim
or as a substring anywhere in the training pool.

Punjabi is the constraint everywhere in this project, and it is why Dakshina is
here. The project's own train splits hold **42** genuinely romanized Punjabi
rows. Dakshina contributes about **4,700** more. Dakshina reserves its `dev`
half for evaluating transliteration (FR-5) and only its `test` half trains this
classifier, so no row is both trained on and evaluated on for any task.

The remaining honest caveat: Dakshina is Wikipedia text that annotators were
asked to romanize, so its spelling is more consistent than a WhatsApp forward's.
The model therefore sees a tidier Punjabi than it is later asked about, and the
two are reported separately rather than averaged -- 0.9908 on MultiClaim dev
against 0.8700 on the hand-typed forwards.

See `scripts/train_roman_lid.py`.
"""

from __future__ import annotations

import os
from pathlib import Path

MODEL_PATH = Path("data/interim/models/roman_lid.joblib")

LABELS = ("en", "hi", "pa")

# Below this the answer is too weak to act on. Lower than it looks: the
# alternative to a weak answer here is `other`, which is a refusal to serve the
# user at all, and a wrong guess that still routes to transliteration is
# recoverable in a way a refusal is not.
DEFAULT_FLOOR = 0.40


class ModelUnavailable(RuntimeError):
    """The classifier has not been trained yet."""


def build_pipeline(seed: int = 42):
    """Char n-gram TF-IDF into logistic regression.

    `class_weight="balanced"` is doing real work: English outnumbers Punjabi by
    about 70 to 1 in the training pool, and without it the model would learn
    that answering `en` is almost always right -- which is exactly the failure
    mode this class exists to fix.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(1, 5),
            min_df=2,
            max_features=200_000,
            sublinear_tf=True,
            lowercase=True,
        )),
        ("clf", LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=seed,
        )),
    ])


class RomanizedLID:
    """Loads a trained char n-gram classifier. Training lives in scripts/."""

    name = "roman_lid"
    impl = "chargram"

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
                    f"`python scripts/train_roman_lid.py`."
                )
            import joblib

            self._model = joblib.load(self.model_path)
        return self._model

    def identify(self, text: str) -> tuple[str, float]:
        """Return `(lang, confidence)` for Latin-script input."""
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return "other", 0.0
        model = self._load()
        probabilities = model.predict_proba([cleaned])[0]
        best = int(probabilities.argmax())
        label = str(model.classes_[best])
        score = float(probabilities[best])
        return (label, score) if score >= self.floor else ("other", score)
