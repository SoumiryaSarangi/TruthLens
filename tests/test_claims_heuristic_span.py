"""The served claims stage: heuristic gate, span-model sentence choice (FR-6, FR-7).

The span model is replaced by a fake tagger, so these run in CI without torch.
"""

from __future__ import annotations

from claims.heuristic import HeuristicClaims
from claims.heuristic_span import HeuristicSpanClaims, sentence_shares
from pipeline.contracts import Preprocessed, Trace


def _trace(text: str) -> Trace:
    trace = Trace(request_id="t")
    trace.pre = Preprocessed(original=text, normalized=text, lang="hi", script="latn",
                             script_purity=1.0)
    return trace


class FakeTagger:
    """Tags every token of any sentence containing one of `claim_words`."""

    def __init__(self, text: str, claim_words: tuple[str, ...]):
        self.tags: list[str] = []
        for sentence in text.replace("!!", "!!\n").replace(". ", ".\n").splitlines():
            words = sentence.split()
            hit = any(w in sentence for w in claim_words)
            self.tags += ["B-CLAIM" if hit else "O"] + ["I-CLAIM" if hit else "O"] * (len(words) - 1)
        self.calls = 0

    def tag(self, tokens):
        self.calls += 1
        assert len(tokens) == len(self.tags)
        return self.tags


RANT = ("Dosto dhyan se padho!! Ye mat bhoolna. Nimbu paani peene se cancer theek "
        "ho jata hai aur hospital wale ye baat chhupate hain.")


def test_a_rant_yields_only_its_claim_sentence():
    claims = HeuristicSpanClaims(tagger=FakeTagger(RANT, ("cancer",)))
    trace = claims.extract(_trace(RANT))
    assert [c.text for c in trace.claims] == [
        "Nimbu paani peene se cancer theek ho jata hai aur hospital wale ye baat chhupate hain."]
    assert trace.unchecked_claims == []


def test_the_heuristic_alone_would_have_checked_the_filler():
    trace = HeuristicClaims().extract(_trace(RANT))
    assert "Dosto dhyan se padho!!" in [c.text for c in trace.claims]


def test_one_candidate_sentence_never_reaches_the_model():
    """A one-sentence AVeriTeC claim must be extracted exactly as before."""
    text = "Sarkar ne announce kiya hai ki har student ko 6000 rupaye milenge"
    tagger = FakeTagger(text, ())
    served = HeuristicSpanClaims(tagger=tagger).extract(_trace(text))
    plain = HeuristicClaims().extract(_trace(text))
    assert tagger.calls == 0
    assert [c.text for c in served.claims] == [c.text for c in plain.claims]


def test_nothing_tagged_still_verifies_one_sentence_not_all():
    claims = HeuristicSpanClaims(tagger=FakeTagger(RANT, ()))
    trace = claims.extract(_trace(RANT))
    assert len(trace.claims) == 1


def test_check_worthiness_is_the_heuristic():
    claims = HeuristicSpanClaims(tagger=FakeTagger("x", ()))
    assert claims.check_worthy(_trace("Good morning, stay blessed 🙏")) is False
    assert claims.check_worthy(_trace(RANT)) is True


def test_sentence_shares_align_by_character_offset():
    text = "aa bb cc dd. ee ff gg hh."
    tags = ["O", "O", "O", "O", "B-CLAIM", "I-CLAIM", "O", "O"]
    assert sentence_shares(text, ["aa bb cc dd.", "ee ff gg hh."], tags) == [0.0, 0.5]
