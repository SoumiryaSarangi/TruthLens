"""Contract tests. SYSTEM_DESIGN.md §12.

These run in CI, where there is no torch, which is why `pydantic` is in the
core lock. Their job is to catch the single most damaging kind of drift: the
pipeline's label strings quietly disagreeing with `src/data/labels.py`.
"""

from __future__ import annotations

import pathlib

import pytest
from pydantic import ValidationError

from data.labels import STANCE_3CLASS, VERDICT_5CLASS
from data.script_id import SCRIPTS
from data.splits import LANGS
from pipeline.contracts import (
    Claim,
    ClaimResult,
    Event,
    FactCheckMatch,
    Lang,
    Passage,
    Preprocessed,
    Script,
    Stance,
    Trace,
    Verdict,
)

# -----------------------------------------------------------------------------
# The literals must match the registry, not merely look like it
# -----------------------------------------------------------------------------


def test_verdict_matches_label_registry():
    assert set(Verdict.__args__) == set(VERDICT_5CLASS)


def test_stance_matches_label_registry():
    assert set(Stance.__args__) == set(STANCE_3CLASS)


def test_script_matches_detector():
    """No `mixed`. detect_script returns exactly these three."""
    assert set(Script.__args__) == set(SCRIPTS)


def test_lang_is_split_langs_plus_runtime_other():
    """`other` is runtime-only and must never be a valid split value."""
    assert set(Lang.__args__) == set(LANGS) | {"other"}
    assert "other" not in LANGS


# -----------------------------------------------------------------------------
# Round-trips
# -----------------------------------------------------------------------------


def _claim_result(**over):
    base = dict(
        claim=Claim(claim_id="c1", text="a claim"),
        path="evidence",
        verdict="Refuted",
        confidence=0.7,
        abstained=False,
        explanation="because [1]",
        explanation_source="template",
        explanation_lang="en",
        cited=["e1"],
    )
    base.update(over)
    return ClaimResult(**base)


@pytest.mark.parametrize("model,kwargs", [
    (Preprocessed, dict(original="x", normalized="x", lang="en", script="latn",
                        script_purity=1.0)),
    (Claim, dict(claim_id="c1", text="t")),
    (Passage, dict(passage_id="e1", doc_id="d1", text="t", retrieval_score=1.0)),
    (Event, dict(stage="retrieval", impl="bm25", ms=1.0)),
    (FactCheckMatch, dict(factcheck_id="f1", score=0.9, verdict="Refuted", title="t",
                          url="u", publisher="p", lang="en")),
])
def test_model_round_trips(model, kwargs):
    obj = model(**kwargs)
    assert model.model_validate(obj.model_dump()) == obj


def test_trace_round_trips_with_nested_results():
    t = Trace(request_id="r1", results=[_claim_result()])
    t.record("retrieval", "bm25", 12.5, "degraded: dense->bm25")
    assert Trace.model_validate(t.model_dump()) == t
    assert t.events[0].note == "degraded: dense->bm25"


# -----------------------------------------------------------------------------
# Invariants
# -----------------------------------------------------------------------------


def test_abstained_result_cannot_carry_generated_prose():
    """SYSTEM_DESIGN.md §2 and §11.

    The point of abstaining is that the system does not stand behind the
    answer; fluent generated text arguing for it undercuts exactly that. The
    contract refuses rather than relying on every generator to remember.
    """
    with pytest.raises(ValidationError, match="template"):
        _claim_result(abstained=True, explanation_source="generated")


def test_abstained_result_may_carry_a_template_explanation():
    assert _claim_result(abstained=True, explanation_source="template").abstained


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_confidence_must_be_a_probability(bad):
    with pytest.raises(ValidationError):
        _claim_result(confidence=bad)


def test_unknown_verdict_is_rejected():
    with pytest.raises(ValidationError):
        _claim_result(verdict="Probably")


def test_script_purity_is_bounded():
    with pytest.raises(ValidationError):
        Preprocessed(original="x", normalized="x", lang="en", script="latn",
                     script_purity=1.5)


MODEL_LIBS = {"torch", "transformers", "sentence_transformers", "faiss", "rank_bm25"}


def test_no_module_in_src_imports_a_model_library_at_top_level():
    """SYSTEM_DESIGN.md §3: stages import models lazily.

    CI installs the core lock, which has no torch, so a single top-level
    `import torch` anywhere under src/ turns the whole suite red. Checked
    statically rather than by importing, because importing is exactly what
    would fail.
    """
    import ast

    root = pathlib.Path(__file__).resolve().parents[1] / "src"
    offenders = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:                       # top level only; nested is fine
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            hit = names & MODEL_LIBS
            if hit:
                offenders.append(f"{path.relative_to(root)}:{node.lineno} imports {sorted(hit)}")

    assert not offenders, (
        "model libraries imported at module scope under src/ — CI runs on the core "
        "lock with no torch and will fail:\n  " + "\n  ".join(offenders)
    )
