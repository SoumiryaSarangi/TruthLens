"""Dumb baselines.

CLAUDE.md: "Compare every model against the dumb baseline in the same table.
A model without a baseline comparison is not a result."

The important design point: a baseline here *generates a predictions JSONL*,
it does not compute metrics. Its numbers then travel the exact same path
through evaluate.py as a model's. A baseline scored by a second code path is
not a control, it is a second chance to be wrong in a different way.

Every baseline is deterministic given the seed, so the comparison row in a
results table is reproducible.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from typing import Any

from common.seeds import SEED


class UnknownBaseline(ValueError):
    pass


def majority_class(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED, **_: Any,
) -> list[dict[str, Any]]:
    """Predict the most frequent gold label for everything.

    The honest floor for any classification result. If a model cannot beat
    this, it has learned nothing, whatever its accuracy looks like on a skewed
    label distribution.
    """
    labels = [r["label"] for r in split_rows if r.get("label") is not None]
    if not labels:
        raise ValueError(
            "majority_class needs gold labels in the split file, but none of the "
            "rows carry a `label` field."
        )
    winner = Counter(labels).most_common(1)[0][0]
    return [{"uid": r["uid"], "pred": winner} for r in split_rows]


def stratified_random(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED, **_: Any,
) -> list[dict[str, Any]]:
    """Sample predictions from the gold label distribution.

    Harder to beat than majority class on macro-F1, because it at least
    predicts every class sometimes.
    """
    labels = [r["label"] for r in split_rows if r.get("label") is not None]
    if not labels:
        raise ValueError("stratified_random needs gold labels in the split file")
    rng = random.Random(seed)
    return [{"uid": r["uid"], "pred": rng.choice(labels)} for r in split_rows]


def random_rank(
    split_rows: Sequence[dict[str, Any]],
    *,
    seed: int = SEED,
    candidate_ids: Sequence[str] | None = None,
    depth: int = 10,
    **_: Any,
) -> list[dict[str, Any]]:
    """Return a random ranking of the candidate pool for every query.

    The floor for claim matching and evidence retrieval. Recall@10 against a
    corpus of thousands should be near zero; a baseline that is not near zero
    means the candidate pool has been filtered in a way that leaks the answer.
    """
    if not candidate_ids:
        raise ValueError(
            "random_rank needs a candidate pool. Pass candidate_ids= (usually every "
            "gold document id in the split)."
        )
    pool = list(candidate_ids)
    rng = random.Random(seed)
    out: list[dict[str, Any]] = []
    for row in split_rows:
        sample = rng.sample(pool, k=min(depth, len(pool)))
        out.append({
            "uid": row["uid"],
            "ranked_ids": sample,
            "scores": [float(len(sample) - i) for i in range(len(sample))],
        })
    return out


def whole_post_span(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    """Predict the entire post as the claim span (the X-CLAIM baseline).

    Registered now so the name is reserved and configs can reference it, but it
    needs tokenised text which arrives with the Phase 3 loaders.
    """
    raise NotImplementedError(
        "whole_post_span lands in Phase 3 with the X-CLAIM span loaders "
        "(docs/build-plan.md, 'Phase 3 - front of pipeline')."
    )


REGISTRY = {
    "majority_class": majority_class,
    "stratified_random": stratified_random,
    "random_rank": random_rank,
    "whole_post_span": whole_post_span,
}


def get_baseline(name: str):
    try:
        return REGISTRY[name]
    except KeyError:
        raise UnknownBaseline(
            f"Unknown baseline {name!r}. Registered: {sorted(REGISTRY)}. "
            "If this is meant to be a prior run, give its config_hash instead."
        ) from None


def is_registered(name: str) -> bool:
    return name in REGISTRY
