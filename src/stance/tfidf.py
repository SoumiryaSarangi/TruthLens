"""TF-IDF + logistic regression stance, and its claim-only twin (FR-10).

The stance baseline `docs/build-plan.md`'s results log names ("TF-IDF + LR"),
below the BiLSTM and XLM-R models the PRD requires.

## The claim-only twin is the point of this file

The stance gold is DERIVED: every QA answer of a claim inherits that claim's
verdict (`data/labels.py`, `map_averitec_stance`). So every pair from one claim
shares one label, and a model can score well by predicting stance from the claim
ALONE -- learning which claims tend to be false -- without reading the evidence.
That is the same class of shortcut that sank Phase 4's reranker, which learned
to score fact-checks instead of pairs.

`TfidfClaimOnlyStance` sees only the claim. It is trained on the same rows, the
same way. If the full model barely beats it, the full model is not using the
evidence, and that is found in minutes rather than after a GPU run.

## Features

Two vectorisers, claim and evidence, so a word means something different on
each side ("vaccine" in a claim is a topic; in the evidence it may be the
refutation). Word 1-2 grams, sublinear TF. `class_weight="balanced"` because
Refutes is ~2/3 of every split and the metric is macro-F1: unweighted, the model
would buy accuracy by never predicting Neutral.
"""

from __future__ import annotations

from pathlib import Path

from stance.nli import StanceResult

MODELS = Path("data/interim/models")
STANCES = ("Supports", "Refutes", "Neutral")


class StanceModelMissing(RuntimeError):
    """The model has not been trained yet."""


class TfidfStance:
    name = "stance"
    impl = "tfidf"
    claim_only = False

    def __init__(self, model_path: str | Path | None = None, **_: object) -> None:
        default = MODELS / f"stance_{self.impl}.joblib"
        self.model_path = Path(model_path) if model_path else default
        self._model = None

    def _load(self):
        if self._model is None:
            if not self.model_path.is_file():
                raise StanceModelMissing(
                    f"no model at {self.model_path}. Run "
                    f"`python scripts/train_stance_tfidf.py`."
                )
            import joblib
            self._model = joblib.load(self.model_path)
        return self._model

    def label(self, claim: str, passages: list[str]) -> list[StanceResult]:
        if not passages:
            return []
        model = self._load()
        rows = [{"claim": claim, "evidence": p} for p in passages]
        probs = model.predict_proba(rows)
        classes = list(model.classes_)
        out = []
        for row in probs:
            dist = {c: float(row[classes.index(c)]) if c in classes else 0.0
                    for c in STANCES}
            best = max(dist, key=dist.get)
            out.append(StanceResult(best, dist[best], dist))
        return out


class TfidfClaimOnlyStance(TfidfStance):
    """Never sees the evidence. The control for every stance model here."""

    impl = "tfidf_claimonly"
    claim_only = True


def build_pipeline(claim_only: bool):
    """The sklearn pipeline both arms train. Kept here so training and loading
    cannot drift apart."""
    from sklearn.compose import ColumnTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer

    def vectoriser():
        return TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2,
                               max_features=50_000)

    columns = [("claim", vectoriser(), "claim")]
    if not claim_only:
        columns.append(("evidence", vectoriser(), "evidence"))
    features = ColumnTransformer(columns)
    return Pipeline([
        ("frame", FunctionTransformer(_to_frame)),
        ("features", features),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced",
                                   random_state=42)),
    ])


def _to_frame(rows):
    import pandas as pd
    return pd.DataFrame(list(rows))
