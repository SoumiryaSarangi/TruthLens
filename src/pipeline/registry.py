"""Maps `(stage, impl)` to a class. SYSTEM_DESIGN.md §3.

The point of this file: which implementation runs is chosen by pipeline config,
never by editing code. That is what lets a baseline and a model be compared
without touching anything but a YAML file, and it is why every stage is
required to have at least two implementations.

Implementations are registered by import path and constructed lazily, so that
importing the registry never imports torch. CI depends on that.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

STAGES = ("preprocess", "claims", "matching", "retrieval", "stance",
          "aggregate", "generation", "faithfulness")


@dataclass(frozen=True)
class Registration:
    stage: str
    impl: str
    module: str
    cls: str


_REGISTRY: dict[tuple[str, str], Registration] = {}


def register(stage: str, impl: str, module: str, cls: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
    _REGISTRY[(stage, impl)] = Registration(stage, impl, module, cls)


def build(stage: str, impl: str, **kwargs: Any):
    """Import and construct one stage implementation."""
    try:
        reg = _REGISTRY[(stage, impl)]
    except KeyError:
        available = sorted(i for (s, i) in _REGISTRY if s == stage)
        raise ValueError(
            f"no implementation {impl!r} for stage {stage!r}. "
            f"Registered: {available or 'none'}"
        ) from None
    module = importlib.import_module(reg.module)
    return getattr(module, reg.cls)(**kwargs)


def implementations(stage: str) -> list[str]:
    return sorted(i for (s, i) in _REGISTRY if s == stage)


def all_registrations() -> list[Registration]:
    return sorted(_REGISTRY.values(), key=lambda r: (r.stage, r.impl))


# -----------------------------------------------------------------------------
# Phase 1 baselines. Registered by path -- nothing is imported until used.
# -----------------------------------------------------------------------------
register("preprocess", "passthrough", "preprocess.passthrough", "PassthroughPreprocess")
register("preprocess", "full", "preprocess.language", "LanguagePreprocess")
register("preprocess", "hybrid", "preprocess.language", "HybridPreprocess")
register("claims", "passthrough", "claims.passthrough", "PassthroughClaims")
register("claims", "heuristic", "claims.heuristic", "HeuristicClaims")
register("claims", "xlmr", "claims.span_xlmr", "SpanXLMRClaims")
register("matching", "none", "matching.none_matcher", "NoMatcher")
register("retrieval", "bm25", "retrieval.bm25", "BM25Retriever")
register("retrieval", "random", "retrieval.random_retriever", "RandomRetriever")
register("retrieval", "dense", "retrieval.dense", "DenseRetriever")
register("stance", "nli", "stance.nli", "NLIStance")
register("stance", "always_neutral", "stance.baseline", "AlwaysNeutralStance")
register("aggregate", "rule", "pipeline.aggregate", "RuleAggregator")
register("generation", "template", "generation.template", "TemplateExplainer")
register("faithfulness", "stub", "faithfulness.stub", "StubFaithfulness")
