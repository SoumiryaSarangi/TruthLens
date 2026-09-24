"""Publisher ratings -> the 5-class verdict scheme (FR-8).

Pure lookup and string handling, so all of this runs in CI. The cases worth
having are the ones where a plausible implementation is wrong: a substring rule
maps `half true` to Supported and `mostly false` to Refuted-for-the-wrong-reason,
and both look fine while you read them.
"""

from __future__ import annotations

import pytest

from data.labels import VERDICT_5CLASS
from data.verdicts import (
    RATING_TO_VERDICT,
    first_instance_url,
    parse_ratings,
    publisher_from_url,
    rating_to_verdict,
)


def test_every_mapped_verdict_is_in_the_declared_label_set():
    """A verdict outside `VERDICT_5CLASS` would fail contract validation at the
    API boundary, long after the mapping table was edited."""
    for rating, verdict in RATING_TO_VERDICT.items():
        assert verdict in VERDICT_5CLASS, f"{rating!r} -> {verdict!r}"


def test_the_table_never_maps_to_not_a_claim():
    """`NotAClaim` comes from check-worthiness upstream (CLAUDE.md), not from a
    publisher's label. `satire` is the tempting case and is left unmapped."""
    assert "NotAClaim" not in set(RATING_TO_VERDICT.values())
    assert rating_to_verdict(["satire"]) is None


@pytest.mark.parametrize("rating, expected", [
    ("false", "Refuted"),
    ("falso", "Refuted"),
    ("fake", "Refuted"),
    ("true", "Supported"),
    ("misleading", "Conflicting"),
    ("missing context", "Conflicting"),
    ("unverifiable", "NEI"),
])
def test_the_head_of_the_distribution_maps(rating, expected):
    assert rating_to_verdict([rating]) == expected


@pytest.mark.parametrize("rating, expected", [
    # Each of these CONTAINS a string that maps somewhere else. A substring rule
    # would send the first to Supported and the third to Refuted.
    ("half true", "Conflicting"),
    ("mostly false", "Refuted"),
    ("partly false", "Conflicting"),
    ("partiellement faux", "Conflicting"),
])
def test_qualified_ratings_are_not_read_as_their_substrings(rating, expected):
    assert rating_to_verdict([rating]) == expected


def test_matching_is_exact_so_an_unknown_variant_declines():
    """`salah [misleading content]` starts with `salah`, which maps to Refuted.

    Declining costs a fall-through to the evidence path, which is where the
    request would have gone anyway. Mis-mapping puts a confident wrong verdict
    in front of a user.
    """
    assert rating_to_verdict(["salah"]) == "Refuted"
    assert rating_to_verdict(["salah [misleading content]"]) is None


def test_case_and_whitespace_do_not_matter():
    assert rating_to_verdict(["  FALSE "]) == "Refuted"


@pytest.mark.parametrize("ratings", [[], None, [""], ["not a real rating"]])
def test_nothing_mappable_declines(ratings):
    assert rating_to_verdict(ratings) is None


def test_disagreeing_ratings_decline_rather_than_pick_one():
    """Two publishers reaching opposite conclusions is not evidence for either."""
    assert rating_to_verdict(["true", "false"]) is None


def test_agreeing_ratings_still_map():
    assert rating_to_verdict(["false", "falso", "fake"]) == "Refuted"


def test_an_unmappable_rating_beside_a_mappable_one_does_not_block_it():
    """The tail is 39 languages of long-tail wording; one unknown label sitting
    next to `false` must not cost the verdict."""
    assert rating_to_verdict(["false", "some untranslated label"]) == "Refuted"


# -----------------------------------------------------------------------------
# The columns nothing read until Phase 4
# -----------------------------------------------------------------------------


def test_parse_ratings_reads_the_list_literal_the_column_holds():
    assert parse_ratings("['false', 'Misleading']") == ["false", "misleading"]


def test_an_unparseable_ratings_cell_is_kept_as_one_label():
    """A publisher whose rating contains a quote is still a rating."""
    assert parse_ratings("it's false") == ["it's false"]


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_an_empty_ratings_cell_is_no_ratings(raw):
    assert parse_ratings(raw) == []


def test_first_instance_url_reads_the_timestamp_url_pairs():
    raw = "[(1622332800.0, 'https://www.politifact.com/factchecks/2021/jun/07/x/')]"
    assert first_instance_url(raw) == (
        "https://www.politifact.com/factchecks/2021/jun/07/x/")


def test_first_instance_url_takes_the_first_of_several():
    raw = "[(1.0, 'https://a.example/one'), (2.0, 'https://b.example/two')]"
    assert first_instance_url(raw) == "https://a.example/one"


@pytest.mark.parametrize("raw", ["", None, "[]", "not a literal"])
def test_no_instances_means_no_url(raw):
    assert first_instance_url(raw) is None


@pytest.mark.parametrize("url, expected", [
    ("https://www.politifact.com/factchecks/2021/x/", "politifact.com"),
    ("https://factly.in/some-check", "factly.in"),
    ("http://TEYIT.ORG/a?b=c", "teyit.org"),
    ("https://factual.afp.com/", "factual.afp.com"),
])
def test_publisher_is_the_domain_without_www(url, expected):
    """MultiClaim has no publisher column, and FR-8's answer is "Already checked
    by X", so X has to come from the only publisher identity in the data."""
    assert publisher_from_url(url) == expected


@pytest.mark.parametrize("url", ["", None])
def test_no_url_means_no_publisher(url):
    assert publisher_from_url(url) is None
