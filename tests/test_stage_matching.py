"""The claim-matching stage (FR-8).

Everything here runs in CI: the pieces that need an index, torch or rank_bm25
are exercised through their refusal paths, and the decision logic is pure.

The thing most worth pinning is that the matcher **declines** rather than
improvising. Phase 4 measured that the bi-encoder score separates a right match
from a wrong one poorly -- at tau 0.90 the fast path fires on 1.7% of posts and
still cites the wrong fact-check 18% of the time -- so every branch that could
turn a doubtful match into a confident answer is a branch worth a test.
"""

from __future__ import annotations

import json

import pytest

from matching.factcheck import FactCheckMatcher, FactCheckMeta, IndexUnavailable
from matching.rerankers import RerankerUnavailable, XLMRReranker, _rerank_with
from matching.rerankers import build as build_reranker
from pipeline.contracts import Claim

META = {
    "100": FactCheckMeta(title="Photo shows Louis Armstrong as a child",
                         text="Photo shows Louis Armstrong as a child",
                         url="https://factly.in/a", publisher="factly.in",
                         verdict="Refuted", lang="en"),
    "200": FactCheckMeta(title="Unmappable rating", text="Unmappable rating",
                         url="https://teyit.org/b", publisher="teyit.org",
                         verdict=None, lang="other"),
    "300": FactCheckMeta(title="A Hindi check", text="A Hindi check",
                         url="https://factly.in/c", publisher="factly.in",
                         verdict="Conflicting", lang="hi"),
}


@pytest.fixture
def matcher():
    return FactCheckMatcher()


# -----------------------------------------------------------------------------
# Turning a ranking into an answer
# -----------------------------------------------------------------------------


def test_the_top_candidate_becomes_the_match(matcher):
    match = matcher._to_match([("100", 0.81), ("300", 0.60)], META)
    assert match is not None
    assert match.factcheck_id == "100"
    assert match.score == pytest.approx(0.81)
    assert match.verdict == "Refuted"
    assert match.publisher == "factly.in"
    assert match.lang == "en"


def test_an_unmappable_rating_declines_rather_than_guessing(matcher):
    """20.8% of the pool carries a rating outside the mapping. The fast path
    cannot answer those, and NEI would be a worse answer than going to look."""
    assert matcher._to_match([("200", 0.95)], META) is None


def test_it_does_not_walk_past_the_top_candidate(matcher):
    """Taking rank 2 when rank 1 has no mappable rating would answer with a
    match the model judged INFERIOR, on a lower score that is more likely wrong
    -- and it would be a decision no eval ever measured, because the predictions
    file carries the retriever's ranking."""
    assert matcher._to_match([("200", 0.95), ("100", 0.90)], META) is None


def test_an_id_missing_from_the_metadata_declines(matcher):
    assert matcher._to_match([("999", 0.99)], META) is None


def test_no_candidates_declines(matcher):
    assert matcher._to_match([], META) is None


def test_a_language_outside_en_hi_pa_becomes_other(matcher):
    """`Lang` is en|hi|pa|other and the pool covers 39 languages -- 42,899 of
    its 78,077 fact-checks are outside the three. An unmapped value here would
    fail contract validation at the API boundary."""
    meta = dict(META)
    meta["400"] = FactCheckMeta(title="t", text="t", url="https://x.example",
                                publisher="x.example", verdict="Refuted", lang="de")
    assert matcher._to_match([("400", 0.9)], meta).lang == "other"


def test_a_missing_url_or_publisher_still_produces_a_valid_match(matcher):
    """Both fields are required by the contract and neither is worth declining
    over; measured, all 78,077 pool fact-checks do have a URL."""
    meta = {"500": FactCheckMeta(title="t", text="t", url=None, publisher=None,
                                 verdict="Refuted", lang="en")}
    match = matcher._to_match([("500", 0.9)], meta)
    assert match.url == ""
    assert match.publisher == "unknown"


def test_the_threshold_is_not_applied_by_the_matcher(matcher):
    """tau_match belongs to the orchestrator (SYSTEM_DESIGN 6). Gating here
    would make every fast-path eval measure one operating point and nothing
    else, when the whole result is the curve across operating points."""
    assert matcher._to_match([("100", 0.01)], META) is not None


# -----------------------------------------------------------------------------
# Configuration and refusals
# -----------------------------------------------------------------------------


def test_the_trace_records_which_stack_actually_ran():
    """"factcheck" would read the same for a raw bi-encoder and a reranked one,
    and those are the two arms of this phase's ablation."""
    assert FactCheckMatcher().impl == "bge_m3"
    assert FactCheckMatcher(reranker="xlmr").impl == "bge_m3+xlmr"
    assert FactCheckMatcher(retriever="bm25_factcheck").impl == "bm25_factcheck"


def test_an_ungated_matcher_says_so_in_the_trace():
    """SYSTEM_DESIGN 11: degrade, record it, never make up a verdict."""
    assert "no reranker" in FactCheckMatcher().note
    assert FactCheckMatcher(reranker="nli").note is None


def test_a_missing_metadata_sidecar_refuses_and_says_how_to_build_it(tmp_path):
    stage = FactCheckMatcher(index_dir=tmp_path)
    with pytest.raises(IndexUnavailable, match="build_factcheck_meta"):
        stage._load_meta()


def test_metadata_is_loaded_once(tmp_path):
    (tmp_path / "factcheck_meta.jsonl").write_text(
        json.dumps({"id": "1", "title": "t", "text": "t", "url": "u",
                    "publisher": "p", "verdict": "Refuted", "lang": "en"}) + "\n",
        encoding="utf-8",
    )
    stage = FactCheckMatcher(index_dir=tmp_path)
    assert stage._load_meta() is stage._load_meta()


def test_top1_takes_a_claim_object(monkeypatch, tmp_path):
    """The stage contract is `top1(claim) -> FactCheckMatch | None`."""
    stage = FactCheckMatcher(index_dir=tmp_path)
    monkeypatch.setattr(stage, "_load_meta", lambda: META)
    monkeypatch.setattr(stage, "rank_batch", lambda texts: [[("100", 0.7)]])
    match = stage.top1(Claim(claim_id="c1", text="anything"))
    assert match.factcheck_id == "100"


# -----------------------------------------------------------------------------
# Rerankers
# -----------------------------------------------------------------------------


def test_reranking_reorders_by_the_new_score_not_the_old_one():
    """The point of the stage: the retriever's order must be able to change."""
    def score(pairs):
        return [0.1, 0.9]

    out = _rerank_with(score, ["post"], [[("a", "text a"), ("b", "text b")]])
    assert out == [[("b", 0.9), ("a", 0.1)]]


def test_scores_are_computed_in_one_batched_call():
    """A transformer's per-row cost is mostly launch overhead; Phase 2 measured
    the difference between one call and many in minutes."""
    calls = []

    def score(pairs):
        calls.append(len(pairs))
        return [0.5] * len(pairs)

    _rerank_with(score, ["p1", "p2"], [[("a", "x"), ("b", "y")], [("c", "z")]])
    assert calls == [3]


def test_candidates_stay_with_their_own_query():
    """Flatten-score-regroup is where an off-by-one would silently attach one
    post's scores to another post's candidates."""
    def score(pairs):
        return [float(i) for i in range(len(pairs))]

    out = _rerank_with(score, ["p1", "p2"], [[("a", "x"), ("b", "y")], [("c", "z")]])
    assert out[0] == [("b", 1.0), ("a", 0.0)]
    assert out[1] == [("c", 2.0)]


def test_ties_are_broken_by_id_so_a_run_is_reproducible():
    """A tie resolved by input order would resolve by the retriever's ranking
    without saying so, which hides how much the reranker actually changed."""
    def score(pairs):
        return [0.5, 0.5, 0.5]

    out = _rerank_with(score, ["p"], [[("c", "x"), ("a", "y"), ("b", "z")]])
    assert [doc_id for doc_id, _ in out[0]] == ["a", "b", "c"]


def test_an_empty_candidate_list_survives():
    out = _rerank_with(lambda pairs: [], ["p"], [[]])
    assert out == [[]]


def test_an_untrained_reranker_refuses_and_says_how_to_train_one(tmp_path):
    stage = XLMRReranker(adapter=tmp_path / "not-trained")
    assert stage.available is False
    with pytest.raises(RerankerUnavailable, match=r"train_reranker.py"):
        stage._load()


def test_an_unknown_reranker_is_refused_with_the_registered_names():
    with pytest.raises(ValueError, match="nli"):
        build_reranker("magic")


@pytest.mark.parametrize("impl", ["nli", "xlmr"])
def test_the_registered_rerankers_build_without_importing_torch(impl):
    """Construction must stay free on a machine without torch; CI depends on
    it (tests/test_contracts.py enforces the same rule statically)."""
    assert build_reranker(impl) is not None
