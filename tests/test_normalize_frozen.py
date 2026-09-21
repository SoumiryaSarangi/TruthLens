"""Pins the hashing normaliser's current behaviour, bugs included.

`data.normalize.normalize_for_hashing` computes `text_sha1` for the frozen
splits. Any change to it rewrites committed split files, invalidates
SPLITS.lock, breaks the CI reproducibility job and stales every results JSON
built against those splits.

So this file exists to make a change to it FAIL LOUDLY and explain the cost,
rather than being discovered when CI goes red for reasons nobody connects to a
regex edit.
"""

from __future__ import annotations

from data.normalize import normalize_for_hashing


def test_forwarded_message_prefix_is_only_partly_stripped():
    """A known bug, kept on purpose. See the comment in src/data/normalize.py.

    The alternation matches `forwarded` before `forwarded message`, leaving the
    word "message" attached. Measured impact: 1 of 9,987 materialised texts.

    If you are here because this test failed: you changed the hashing
    normaliser. That is allowed, but it is a SPLIT REBUILD, not a code fix --
    rebuild data/splits/, update SPLITS.lock, record it in
    docs/split-changelog.md, and re-run every eval whose results reference the
    old split hash.
    """
    assert normalize_for_hashing("Forwarded message: The minister resigned.") == \
        "message: the minister resigned."


def test_plain_forwarded_prefix_is_stripped():
    assert normalize_for_hashing("Forwarded many times: The minister resigned.") == \
        "the minister resigned."


def test_the_model_facing_normaliser_does_not_share_the_bug():
    """preprocess/passthrough.py is free to be correct: nothing is hashed from it."""
    from pipeline.contracts import Trace
    from preprocess.passthrough import PassthroughPreprocess

    pre = PassthroughPreprocess().run(Trace(request_id="t"),
                                      "Forwarded message: The minister resigned.").pre
    assert pre.normalized == "The minister resigned."
