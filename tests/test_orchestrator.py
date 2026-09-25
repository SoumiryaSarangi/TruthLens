"""Golden traces, one per path through the orchestrator. SYSTEM_DESIGN.md §12.

Every test here runs the whole flow with no model weights, using the
`always_neutral` stance baseline and a synthetic knowledge store. That is
deliberate: the paths through the orchestrator -- and especially the
degradation paths -- are where silent wrongness hides, and they must be
testable in CI without a GPU.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from common.io_jsonl import write_jsonl
from pipeline.orchestrator import Orchestrator, PipelineConfig
from retrieval.kb import KnowledgeStore

pytest.importorskip("rank_bm25", reason="rank_bm25 lives in the ML lock")


@pytest.fixture
def kb(tmp_path):
    write_jsonl(tmp_path / "averitec_kb_dev" / "7.jsonl", [
        {"doc_id": "d_gold", "is_gold": True,
         "paragraphs": ["Intro.", "The minister restored 4400 nursing posts in 2020."]},
        {"doc_id": "d1", "is_gold": False, "paragraphs": ["Lemon cake recipe."]},
    ])
    write_jsonl(tmp_path / "averitec_kb_dev" / "9.jsonl", [])     # empty pool
    return tmp_path


def make(kb_root, **over) -> Orchestrator:
    cfg = PipelineConfig(
        stages={"stance": "always_neutral", **over.pop("stages", {})}, **over
    )
    orch = Orchestrator(cfg)
    orch.retriever.store = KnowledgeStore("dev", cache_root=kb_root)
    return orch


# -----------------------------------------------------------------------------
# The evidence path
# -----------------------------------------------------------------------------


def test_evidence_path_produces_a_verdict_with_sources(kb):
    trace = make(kb).verify("Were 4400 nursing posts restored?", claim_idx=7)
    assert len(trace.results) == 1
    res = trace.results[0]
    assert res.path == "evidence"
    assert res.passages, "a verdict must come with the evidence behind it"
    assert res.verdict == "NEI"          # always_neutral stance -> the rule gives NEI
    assert res.explanation_source == "template"
    assert res.cited


def test_trace_records_every_stage_it_ran(kb):
    """FR-22: the UI's evidence trail is rendered from this."""
    trace = make(kb).verify("nursing posts", claim_idx=7)
    stages = {e.stage for e in trace.events}
    assert {"preprocess", "claims", "retrieval", "stance", "aggregate"} <= stages
    assert all(e.ms >= 0 for e in trace.events)


def test_passages_carry_ids_scores_and_highlights(kb):
    res = make(kb).verify("nursing posts restored", claim_idx=7).results[0]
    p = res.passages[0]
    assert p.passage_id == "e1"
    assert p.retrieval_score >= 0
    assert p.highlight is not None and p.highlight[1] > p.highlight[0]


# -----------------------------------------------------------------------------
# Degradation, which must never crash and never invent a verdict
# -----------------------------------------------------------------------------


def test_empty_pool_gives_nei_and_abstains(kb):
    """FR-12: zero passages retrieved is NEI with abstained=true."""
    res = make(kb).verify("anything", claim_idx=9).results[0]
    assert res.verdict == "NEI"
    assert res.abstained is True
    assert res.passages == []
    assert res.explanation_source == "template"


def test_free_text_without_a_pool_abstains_rather_than_guessing(kb):
    """No demo corpus exists yet (SYSTEM_DESIGN.md §7), so say so."""
    trace = make(kb).verify("Some claim with no candidate pool.", claim_idx=None)
    res = trace.results[0]
    assert res.verdict == "NEI" and res.abstained
    assert any("no candidate pool" in (e.note or "") for e in trace.events)


def test_retrieval_failure_degrades_instead_of_raising(kb):
    orch = make(kb)

    def boom(*a, **k):
        raise RuntimeError("index unavailable")

    orch.retriever.topk = boom
    trace = orch.verify("claim", claim_idx=7)
    assert trace.results[0].verdict == "NEI"
    assert any("degraded: retrieval failed" in (e.note or "") for e in trace.events)


def test_stance_failure_degrades_instead_of_raising(kb):
    orch = make(kb)

    def boom(*a, **k):
        raise RuntimeError("model not loaded")

    orch.stance.label = boom
    trace = orch.verify("nursing posts", claim_idx=7)
    assert trace.results[0].verdict == "NEI"
    assert any("degraded: stance failed" in (e.note or "") for e in trace.events)


def test_missing_fast_path_is_recorded_not_hidden(kb):
    """A trace must not imply a fast path was tried and missed."""
    trace = make(kb).verify("nursing posts", claim_idx=7)
    assert any("no fast path" in (e.note or "") for e in trace.events)


# -----------------------------------------------------------------------------
# Short circuits
# -----------------------------------------------------------------------------


def test_empty_input_short_circuits_to_not_a_claim(kb):
    """FR-6: no retrieval runs for something with no claim in it."""
    trace = make(kb).verify("   ", claim_idx=7)
    assert trace.checkworthy is False
    assert trace.results[0].verdict == "NotAClaim"
    assert not any(e.stage == "retrieval" for e in trace.events)


def test_abstention_threshold_is_applied(kb):
    """FR-14. tau_abstain=1.1 forces abstention on every result."""
    res = make(kb, tau_abstain=1.1).verify("nursing posts", claim_idx=7).results[0]
    assert res.abstained is True
    assert res.explanation_source == "template"
    assert "Not confident enough" in res.explanation


def test_abstention_is_off_by_default(kb):
    res = make(kb).verify("nursing posts", claim_idx=7).results[0]
    assert res.abstained is False


def test_config_selects_the_implementation(kb):
    """SYSTEM_DESIGN.md §3: impl choice is config, never a code edit."""
    orch = make(kb, stages={"retrieval": "random"})
    assert orch.retriever.impl == "random"


# -----------------------------------------------------------------------------
# The fast path
#
# SYSTEM_DESIGN.md §12 wants a golden trace per path, and `fast` is the one the
# Phase 1 `none` matcher can never reach. Left untested it would first execute
# in Phase 4, against real MultiClaim data, with nothing pinning its shape.
# A stub matcher exercises it now.
# -----------------------------------------------------------------------------


class _StubMatcher:
    """Always returns a match. Stands in for the Phase 4 matcher."""

    name = "matching"
    impl = "stub"

    def __init__(self, score: float = 0.9):
        self.score = score

    def top1(self, claim):
        from pipeline.contracts import FactCheckMatch

        return FactCheckMatch(
            factcheck_id="fc123", score=self.score, verdict="Refuted",
            title="No, nursing posts were not restored",
            url="https://factcheck.example/fc123",
            publisher="Example FactCheck", lang="en",
        )


def test_fast_path_resolves_from_the_matched_fact_check(kb):
    orch = make(kb, tau_match=0.5)
    orch.matcher = _StubMatcher(score=0.9)

    res = orch.verify("Were nursing posts restored?", claim_idx=7).results[0]
    assert res.path == "fast"
    assert res.verdict == "Refuted"                 # taken from the fact-check
    assert res.match is not None
    assert res.cited == ["fc123"]
    assert "Example FactCheck" in res.explanation   # UI_UX.md §5: "Already checked by"
    assert res.passages == []                       # no retrieval on the fast path


def test_fast_path_is_skipped_when_the_match_is_below_tau(kb):
    """τ_match is what makes the fast path a decision rather than a default."""
    orch = make(kb, tau_match=0.95)
    orch.matcher = _StubMatcher(score=0.9)

    res = orch.verify("Were nursing posts restored?", claim_idx=7).results[0]
    assert res.path == "evidence"
    assert res.match is None


def test_fast_path_does_not_run_retrieval(kb):
    orch = make(kb, tau_match=0.5)
    orch.matcher = _StubMatcher(score=0.9)

    trace = orch.verify("Were nursing posts restored?", claim_idx=7)
    assert not any(e.stage == "retrieval" for e in trace.events)


def test_an_unbounded_match_score_does_not_crash_the_response(kb):
    """`ClaimResult.confidence` is validated to [0, 1] and a match score is not.

    A BM25 score on the fact-check pool is around 20 and a cosine can be
    negative, so assigning one straight through raised a ValidationError at
    request time. It was unreachable only because `NoMatcher` never returned a
    match, which is exactly how it survived three phases.
    """
    orch = Orchestrator(PipelineConfig())
    orch.matcher = _StubMatcher(score=20.47)

    res = orch.verify("Were nursing posts restored?", claim_idx=7).results[0]
    assert res.path == "fast"
    assert res.confidence == 1.0
    # The raw score is not lost: it stays on the match the response carries.
    assert res.match.score == pytest.approx(20.47)


def test_a_negative_match_score_is_clamped_too(kb):
    """Needs a gate that accepts everything: the default tau_match is 0.0, so a
    negative score takes the evidence path and never reaches the clamp."""
    orch = Orchestrator(PipelineConfig(tau_match=-1.0))
    orch.matcher = _StubMatcher(score=-0.3)
    res = orch.verify("Were nursing posts restored?", claim_idx=7).results[0]
    assert res.path == "fast"
    assert res.confidence == 0.0


def test_the_trace_says_the_fast_path_confidence_is_uncalibrated(kb):
    """It is a retrieval score wearing the confidence field's name. Calibration
    is Phase 6 (FR-13, FR-14), and until then the trace has to say so."""
    orch = Orchestrator(PipelineConfig())
    orch.matcher = _StubMatcher(score=0.9)
    trace = orch.verify("Were nursing posts restored?", claim_idx=7)
    assert any(e.note and "uncalibrated" in e.note for e in trace.events)


def test_a_clamped_score_is_recorded_rather_than_silently_adjusted(kb):
    orch = Orchestrator(PipelineConfig())
    orch.matcher = _StubMatcher(score=20.47)
    trace = orch.verify("Were nursing posts restored?", claim_idx=7)
    assert any(e.note and "clamped" in e.note for e in trace.events)


# -----------------------------------------------------------------------------
# The SERVED config, not a test fixture
# -----------------------------------------------------------------------------
# Until Phase 4 `configs/pipeline/dev.yaml` still ran Phase 1 baselines at every
# stage, so everything Phases 2 and 3 built was measured and not served. Nothing
# caught that, because every test built its own PipelineConfig. These load the
# real file.


SERVED = Path("configs/pipeline/dev.yaml")


def test_the_served_config_runs_the_stages_that_were_built():
    """A stage left on its Phase 1 baseline is work that is measured and not
    shipped -- and `claims: passthrough` makes `NotAClaim` unreachable, which is
    the first card in the demo script and the answer to PRD scenario S4."""
    cfg = PipelineConfig.load(SERVED)
    assert cfg.stages["preprocess"] != "passthrough"
    assert cfg.stages["claims"] != "passthrough"
    assert cfg.stages["matching"] != "none"


def test_the_served_tau_match_is_the_one_chosen_on_dev():
    """FR-14 and SYSTEM_DESIGN 6: tau is selected on dev and recorded in the
    served config, where GET /version reports it (FR-21). Pinned so a change is
    deliberate -- the measured curve puts fast-path precision at 81.8% here and
    62.7% at tau 0.70, so this number is a safety decision, not a default."""
    assert PipelineConfig.load(SERVED).tau_match == 0.90


def test_the_served_pipeline_answers_not_a_claim_to_a_greeting():
    """PRD scenario S4, end to end through the served claims stage.

    Preprocess is overridden to `passthrough` because `hybrid` needs the
    romanized-LID model from gitignored data/interim/, and it makes no difference
    here: both produce identical normalized text (measured, 306/306 MultiClaim
    rows). The claims stage is the served one.
    """
    cfg = PipelineConfig.load(SERVED)
    cfg.stages["preprocess"] = "passthrough"
    cfg.stages["matching"] = "none"
    orch = Orchestrator(cfg)
    result = orch.verify("Good morning, stay blessed").results[0]
    assert result.verdict == "NotAClaim"


def test_the_served_pipeline_does_not_reject_a_scheme_rumour():
    """The inversion that end-to-end wiring caught and no metric showed.

    With `claims: nli` -- the arm that WINS macro-F1 on the hand-typed set -- the
    served pipeline answered `NotAClaim` to this, while accepting a Punjabi
    blessing. It rejects 18 of 85 real claims (21.2%), measured. A false
    `NotAClaim` fails the user completely; a false check-worthy costs an NEI on a
    blessing. macro-F1 weights the two errors equally and the product does not.
    """
    cfg = PipelineConfig.load(SERVED)
    cfg.stages["preprocess"] = "passthrough"
    cfg.stages["matching"] = "none"
    orch = Orchestrator(cfg)
    trace = orch.verify(
        "Sarkar ne announce kiya hai ki har student ko 6000 rupaye milenge")
    assert trace.checkworthy is True
    assert trace.results[0].verdict != "NotAClaim"
