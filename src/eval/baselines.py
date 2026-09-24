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
import re
from collections import Counter
from collections.abc import Sequence
from typing import Any

from common.seeds import SEED


class UnknownBaseline(ValueError):
    pass


def majority_class(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED,
    gold_field: str = "label", **_: Any,
) -> list[dict[str, Any]]:
    """Predict the most frequent gold label for everything.

    The honest floor for any classification result. If a model cannot beat
    this, it has learned nothing, whatever its accuracy looks like on a skewed
    label distribution.

    `gold_field` must match the config's, or the baseline predicts from one
    column while being scored against another -- which the harness catches as an
    unknown label, but only because the two label sets happen to be disjoint.
    """
    labels = [r[gold_field] for r in split_rows if r.get(gold_field) is not None]
    if not labels:
        raise ValueError(
            f"majority_class needs gold labels in the split file, but none of the "
            f"rows carry a `{gold_field}` field."
        )
    winner = Counter(labels).most_common(1)[0][0]
    return [{"uid": r["uid"], "pred": winner} for r in split_rows]


def stratified_random(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED,
    gold_field: str = "label", **_: Any,
) -> list[dict[str, Any]]:
    """Sample predictions from the gold label distribution.

    Harder to beat than majority class on macro-F1, because it at least
    predicts every class sometimes.
    """
    labels = [r[gold_field] for r in split_rows if r.get(gold_field) is not None]
    if not labels:
        raise ValueError(f"stratified_random needs gold labels in the split file "
                         f"(`{gold_field}`)")
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


def always_match(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED,
    predictions: dict[str, dict[str, Any]] | None = None, **_: Any,
) -> list[dict[str, Any]]:
    """Take the top-1 match regardless of its score: the fast path with no gate.

    The floor for a fast-path DECISION, and note what it holds fixed. The
    RANKING is the model's own and only the SCORE is destroyed, which is
    deliberate: `random_rank` is already the floor for "can the retriever find
    it" and `task: retrieval` already answers that. The question here is whether
    the score says when to trust the answer, and the only control that isolates
    it is the same ranking carrying an uninformative score.

    Coverage 1.0, precision = Success@1 and false_accept_rate 1.0 are fixed by
    construction. AUCC is Success@1 **in expectation**: every score is identical,
    so each coverage point is an unbiased random subsample and the curve is flat
    only on average. Measured on MultiClaim dev (n=3,153) it lands at 0.4284
    against a Success@1 of 0.4326 -- so read a delta against this baseline as
    carrying a few thousandths of tie-ordering slop. It is deterministic (the
    scorer shuffles with the config's seed), not noise that moves between runs.

    It is the first baseline here that reads the run's own predictions. That
    looks like a loss of independence and is not: independence from the ranking
    would answer the retrieval question, which is a different question with its
    own floor.

    **The constant comes from the run, not from a literal.** The first version
    used 1.0, which is above every cosine and far below a BM25 score. On the BM25
    arm, whose taus span 20 to 400, "the gate removed" then accepted NOTHING and
    the baseline reported coverage 0.0000 where it must report 1.0. Taking the
    run's own maximum keeps the property on any score scale. It cannot be
    infinity, which is not representable in JSON and which the coverage curve
    would record as a threshold.
    """
    if not predictions:
        raise ValueError(
            "always_match needs the run's own predictions; the harness injects "
            "them for task: fast_path."
        )
    ceiling = max(
        (float(s) for pred in predictions.values() for s in pred.get("scores", ())),
        default=1.0,
    )
    out: list[dict[str, Any]] = []
    for row in split_rows:
        pred = predictions.get(row["uid"])
        if pred is None:
            continue
        ranked = list(pred["ranked_ids"])
        out.append({"uid": row["uid"], "ranked_ids": ranked,
                    "scores": [ceiling] * len(ranked)})
    return out


def whole_post_span(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED,
    gold: dict[str, list[str]] | None = None, **_: Any,
) -> list[dict[str, Any]]:
    """Predict the entire post as the claim span (the X-CLAIM baseline).

    Not a straw man. Measured on X-CLAIM dev, 25.8% of gold spans ARE the whole
    post and 52.1% of all tokens are claim tokens -- so this scores recall 1.0
    and precision ~0.52 by construction, for a token F1 near 0.69. A span model
    that merely ties it has learned nothing, which is why PRD 8 requires beating
    it PER LANGUAGE rather than on the average.

    It needs the gold only for its token COUNT per row, not for its tags: the
    prediction is "every token is a claim token", and the harness requires one
    tag per gold token.
    """
    if not gold:
        raise ValueError(
            "whole_post_span needs the span gold to know how many tokens each "
            "post has. It is injected by the harness for task: span."
        )
    return [{"uid": r["uid"], "bio": ["B-CLAIM"] + ["I-CLAIM"] * (len(gold[r["uid"]]) - 1)}
            for r in split_rows if r["uid"] in gold and gold[r["uid"]]]


def longest_sentence(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED,
    texts: dict[str, str] | None = None, **_: Any,
) -> list[dict[str, Any]]:
    """Normalization baseline: return the post's longest sentence.

    The dumb version of "find the claim and state it plainly". A forward's
    longest sentence is very often its substantive one, and any normalizer that
    cannot beat this is doing nothing a `split('.')` could not.
    """
    if not texts:
        raise ValueError(
            "longest_sentence needs the source text, which lives in "
            "data/interim/. Run `make data` if that directory is missing."
        )
    out = []
    for row in split_rows:
        text = texts.get(row["uid"], "")
        # Devanagari/Gurmukhi sentences end in a danda (U+0964), not a full stop.
        parts = [p.strip() for p in re.split(r"[.!?।\n]+", text) if p.strip()]
        out.append({"uid": row["uid"],
                    "normalized": max(parts, key=len) if parts else text.strip()})
    return out


def identity_transliteration(
    split_rows: Sequence[dict[str, Any]], *, seed: int = SEED,
    texts: dict[str, str] | None = None, **_: Any,
) -> list[dict[str, Any]]:
    """Do nothing: hand the romanized text back unchanged.

    The honest floor for FR-5. Its CER is the distance between how people type
    and how the language is written, so it is not just a control -- it is the
    size of the problem, and any transliterator that cannot beat it is adding
    latency and nothing else.

    `texts` is injected by the harness from data/interim/, the same place the
    batch runner reads claim text from. A baseline cannot resolve it alone
    because split files hold ids, not text.
    """
    if not texts:
        raise ValueError(
            "identity_transliteration needs the source text, which lives in "
            "data/interim/. Run `make data` if that directory is missing."
        )
    return [{"uid": r["uid"], "transliterated": texts.get(r["uid"], "")}
            for r in split_rows]


REGISTRY = {
    "majority_class": majority_class,
    "stratified_random": stratified_random,
    "random_rank": random_rank,
    "always_match": always_match,
    "whole_post_span": whole_post_span,
    "identity_transliteration": identity_transliteration,
    "longest_sentence": longest_sentence,
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
