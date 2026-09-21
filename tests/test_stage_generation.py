"""Template explainer. FR-18: it must ALWAYS be able to produce something.

It is the fallback for every failure mode in Phase 6 -- generation unavailable,
timed out, or failing the faithfulness check -- so "it always returns text" is
the property that matters most, ahead of how good the text is.
"""

from __future__ import annotations

import pytest

from generation.template import VERDICT_PHRASE, TemplateExplainer
from pipeline.contracts import Passage


def passages(n=2):
    return [Passage(passage_id=f"e{i}", doc_id=f"http://src/{i}", text="t",
                    retrieval_score=1.0, stance="Refutes" if i % 2 else "Supports")
            for i in range(1, n + 1)]


@pytest.fixture
def gen():
    return TemplateExplainer()


@pytest.mark.parametrize("verdict", list(VERDICT_PHRASE))
def test_every_verdict_has_a_phrase(gen, verdict):
    text, _ = gen.explain(verdict, passages())
    assert text and len(text) > 10


def test_explanation_cites_passage_ids(gen):
    text, cited = gen.explain("Refuted", passages(3))
    assert cited == ["e1", "e2", "e3"]
    assert "[1]" in text and "[3]" in text


def test_citations_are_capped(gen):
    _, cited = TemplateExplainer(max_cited=2).explain("Refuted", passages(5))
    assert len(cited) == 2


def test_it_still_explains_with_no_passages(gen):
    """FR-18: a template explanation always exists."""
    text, cited = gen.explain("NEI", [])
    assert "No sources were retrieved" in text
    assert cited == []


def test_abstained_says_the_system_declined_not_that_evidence_is_missing(gen):
    """UI_UX.md §6: abstained and NEI are different claims about the world."""
    text, _ = gen.explain("Refuted", passages(), abstained=True)
    assert "Not confident enough" in text
    assert "Leaning: refuted" in text


def test_copy_avoids_true_and_false(gen):
    """UI_UX.md §8: the system judges evidence, not truth."""
    for verdict in VERDICT_PHRASE:
        text, _ = gen.explain(verdict, passages())
        lowered = text.lower()
        assert " true" not in lowered and " false" not in lowered
        assert "!" not in text          # no alarm language, even for Refuted
