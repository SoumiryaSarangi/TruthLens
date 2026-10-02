"""Stance over passages -> one verdict. SYSTEM_DESIGN.md §6.

The Phase 1 aggregator is a fixed rule, fully specified, so it is a real floor
rather than a tuned thing pretending to be one:

    max P(Supports) >= t and max P(Refutes) >= t   -> Conflicting
    max P(Supports) >= t                           -> Supported
    max P(Refutes)  >= t                           -> Refuted
    otherwise                                      -> NEI

Confidence is the winning probability. It is NOT calibrated -- Phase 6 replaces
this with a learned aggregator plus temperature scaling, and reports ECE before
and after. Until then, treat the number as a score, not a probability, and note
that abstention thresholds chosen against it mean little.

This stays registered as `aggregate_rule` after Phase 6 so the improvement is
measurable rather than asserted.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_THRESHOLD = 0.5
MODELS = Path("data/interim/models")


@dataclass(frozen=True)
class Aggregated:
    verdict: str
    confidence: float
    max_supports: float
    max_refutes: float
    # The full verdict distribution, when the aggregator has one. The rule has
    # none -- its confidence is a winning stance probability, not a P(verdict) --
    # and says so by leaving this None rather than inventing a distribution.
    probs: dict[str, float] | None = field(default=None)


class RuleAggregator:
    name = "aggregate"
    impl = "rule"

    def __init__(self, threshold: float = DEFAULT_THRESHOLD, **_: object):
        self.threshold = threshold

    def aggregate(self, stance_probs: list[dict[str, float]],
                  dense: Sequence[float | None] | None = None) -> Aggregated:
        """`stance_probs` is one dict per retrieved passage. `dense` is ignored."""
        if not stance_probs:
            # FR-12: no evidence is not a verdict. The caller also marks it
            # abstained; returning NEI here keeps that decision in one place.
            return Aggregated("NEI", 0.0, 0.0, 0.0)

        sup = max(p.get("Supports", 0.0) for p in stance_probs)
        ref = max(p.get("Refutes", 0.0) for p in stance_probs)
        t = self.threshold

        if sup >= t and ref >= t:
            return Aggregated("Conflicting", max(sup, ref), sup, ref)
        if sup >= t:
            return Aggregated("Supported", sup, sup, ref)
        if ref >= t:
            return Aggregated("Refuted", ref, sup, ref)

        # Nothing was confident either way. Confidence is how strongly the
        # evidence declined to commit, which is what an abstention threshold
        # should later be applied to.
        return Aggregated("NEI", 1.0 - max(sup, ref), sup, ref)


# -----------------------------------------------------------------------------
# The learned aggregator (Phase 6, FR-11)
# -----------------------------------------------------------------------------
#
# Why the rule had to go, measured in Phase 5: max P(Supports) and max
# P(Refutes) over k passages means ONE passage of ten decides, and both maxima
# clearing 0.5 means Conflicting. A stance model that ignores evidence gives
# every passage one distribution and so can never trigger Conflicting -- which is
# why the claim-only control won the verdict (0.2514). The features below see the
# whole distribution over the k passages, in rank order.

VERDICTS = ("Supported", "Refuted", "Conflicting", "NEI")

FEATURE_NAMES = (
    "mean_s", "mean_r", "mean_n", "max_s", "max_r", "max_n", "min_s", "min_r",
    "frac_s50", "frac_r50", "rankw_s_minus_r", "top1_s", "top1_r", "top1_n",
    "max_s_x_max_r", "dense_max", "dense_mean", "has_dense", "frac_passages",
)


def features(stance_probs: Sequence[dict[str, float]],
             dense: Sequence[float | None] | None = None, k: int = 10) -> list[float]:
    """One fixed-length vector from the stance over the top-`k` passages.

    Passages arrive best-first and only the first `k` are read, so the vector
    depends on RANK, never on how many extra passages a caller happened to pass.
    The SAME function builds training rows (offline, from cached passages) and
    serving rows (in the orchestrator), so the two cannot drift apart.
    """
    probs = list(stance_probs)[:k]
    dvals = [d for d in (list(dense or [])[:k]) if d is not None]
    n = len(probs)
    if not n:
        return [0.0] * len(FEATURE_NAMES)
    s = [p.get("Supports", 0.0) for p in probs]
    r = [p.get("Refutes", 0.0) for p in probs]
    u = [p.get("Neutral", 0.0) for p in probs]
    # Discounted like nDCG: rank 1 counts most, and a passage at rank 10 still
    # counts -- unlike the max, which lets rank 10 outvote ranks 1-9.
    w = [1.0 / math.log2(i + 2) for i in range(n)]
    rankw = sum(wi * (si - ri) for wi, si, ri in zip(w, s, r)) / sum(w)
    return [
        sum(s) / n, sum(r) / n, sum(u) / n, max(s), max(r), max(u), min(s), min(r),
        sum(v >= 0.5 for v in s) / n, sum(v >= 0.5 for v in r) / n, rankw,
        s[0], r[0], u[0], max(s) * max(r),
        max(dvals) if dvals else 0.0, sum(dvals) / len(dvals) if dvals else 0.0,
        1.0 if dvals else 0.0, n / k,
    ]


# Which stance distributions an artifact reads. "" is the plain Supports /
# Refutes / Neutral keys every stance stage emits; "xlmr:" is XLM-R's
# distribution as carried by the combined stage (`stance/combined.py`), which
# shows NLI's labels but lets the verdict use XLM-R's prior too.
SOURCES = {"base": "", "xlmr": "xlmr:"}


def source_view(stance_probs: Sequence[dict[str, float]],
                prefix: str) -> list[dict[str, float]]:
    """One source's per-passage distributions, under plain keys."""
    if not prefix:
        return [{k: v for k, v in p.items() if ":" not in k} for p in stance_probs]
    return [{k[len(prefix):]: v for k, v in p.items() if k.startswith(prefix)}
            for p in stance_probs]


def feature_names(sources: Sequence[str] = ("",)) -> tuple[str, ...]:
    return tuple(f"{prefix}{name}" for prefix in sources for name in FEATURE_NAMES)


def multi_features(stance_probs: Sequence[dict[str, float]],
                   dense: Sequence[float | None] | None = None, k: int = 10,
                   sources: Sequence[str] = ("",)) -> list[float]:
    """`features()` per source, concatenated. One source == `features()` exactly."""
    out: list[float] = []
    for prefix in sources:
        out += features(source_view(stance_probs, prefix), dense, k=k)
    return out


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    scaled = [x / temperature for x in logits]
    top = max(scaled)
    exps = [math.exp(x - top) for x in scaled]
    total = sum(exps)
    return [e / total for e in exps]


class AggregatorMismatch(RuntimeError):
    """The artifact was trained on a different stance model or feature set."""


class LearnedAggregator:
    """Logistic regression over `features()`, temperature-scaled (FR-11, FR-13).

    Loads `data/interim/models/aggregator_<stance>/model.joblib`, written by
    `scripts/train_aggregator.py`. The artifact records the stance model and the
    feature names it was trained on; the orchestrator checks the stance before
    serving, because an aggregator trained on XLM-R's probabilities reads NLI's
    as noise and would never say so.
    """

    name = "aggregate"
    impl = "learned"

    def __init__(self, path: str | Path | None = None, stance: str | None = None,
                 temperature: float | None = None, **_: object) -> None:
        if path is None:
            if stance is None:
                raise ValueError("LearnedAggregator needs `path` or `stance`")
            path = MODELS / f"aggregator_{stance}" / "model.joblib"
        self.path = Path(path)
        # Override the fitted temperature. Exists for ONE comparison: FR-13 asks
        # for ECE before and after scaling, and "before" is this artifact at T=1.
        self._temperature = temperature
        self._artifact: dict | None = None

    def _load(self) -> dict:
        if self._artifact is None:
            if not self.path.is_file():
                raise FileNotFoundError(
                    f"no aggregator at {self.path}. Train one with "
                    "`python scripts/train_aggregator.py`."
                )
            import joblib

            art = joblib.load(self.path)
            art.setdefault("sources", ("",))         # artifacts from before sources
            if tuple(art["features"]) != feature_names(art["sources"]):
                raise AggregatorMismatch(
                    f"{self.path} was trained on features {art['features']}, this "
                    f"code computes {feature_names(art['sources'])}. Retrain it."
                )
            self._artifact = art
        return self._artifact

    @property
    def available(self) -> bool:
        return self.path.is_file()

    @property
    def stance(self) -> str:
        return self._load()["stance"]

    @property
    def temperature(self) -> float:
        if self._temperature is not None:
            return float(self._temperature)
        return float(self._load()["temperature"])

    def logits(self, stance_probs, dense=None) -> list[float]:
        art = self._load()
        x = multi_features(stance_probs, dense, k=art["k"], sources=art["sources"])
        raw = art["model"].decision_function([x])[0]
        # sklearn orders by `classes_`; the distribution is reported in VERDICTS order.
        by_class = dict(zip(art["model"].classes_, raw, strict=True))
        return [float(by_class.get(v, -1e9)) for v in VERDICTS]

    def aggregate(self, stance_probs: list[dict[str, float]],
                  dense: Sequence[float | None] | None = None) -> Aggregated:
        if not stance_probs:
            return Aggregated("NEI", 0.0, 0.0, 0.0)          # FR-12, as the rule
        dist = softmax(self.logits(stance_probs, dense), self.temperature)
        probs = dict(zip(VERDICTS, dist, strict=True))
        verdict = max(probs, key=probs.get)
        return Aggregated(
            verdict, probs[verdict],
            max(p.get("Supports", 0.0) for p in stance_probs),
            max(p.get("Refutes", 0.0) for p in stance_probs),
            probs=probs,
        )

