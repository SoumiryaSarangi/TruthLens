"""Faithfulness stub. Phase 6 replaces it.

One property matters now: it returns None, not a number. A stub returning 1.0
would put a confident-looking score into every results JSON for a check that
never ran, and it would eventually be reported as if it meant something.
"""

from __future__ import annotations

from faithfulness.stub import StubFaithfulness


def test_stub_returns_none_not_a_score():
    assert StubFaithfulness().score("an explanation", ["evidence"]) is None


def test_stub_returns_none_even_with_no_evidence():
    assert StubFaithfulness().score("an explanation", []) is None
