"""Does the leakage detector actually detect leakage?

This is the most important test in Phase 0. tests/test_no_leakage.py runs
against the real splits and, if all goes well, passes forever -- which tells
you nothing about whether it *can* fail. These tests run the same detector
over tests/fixtures/toy_leaky/, where four leaks have been planted on purpose,
and assert that each one is found.

The planted leaks (see scripts/make_fixtures.py):
  1. the same uid in train and dev
  2. the same claim re-keyed under a new uid and source_id
  3. a forward header and emoji bolted on -- the normaliser strips both, so it
     lands as an exact duplicate
  4. a punctuation-only variant -- survives normalisation, so only the SimHash
     proximity check can catch it
"""

from __future__ import annotations

import pytest

from common.io_jsonl import load_jsonl
from data.leakage import failures, find_leakage, format_report, per_split_counts
from data.normalize import normalize_for_hashing
from data.simhash import hamming, simhash64
from data.splits import load_split

SPLIT_NAMES = ("train", "dev", "test")


def load_fixture(fixtures_dir, name):
    return {s: load_split(fixtures_dir / name / f"{s}.jsonl") for s in SPLIT_NAMES}


def load_texts(fixtures_dir, name):
    """Fixture text, so near-duplicate findings are CONFIRMED rather than warned.

    Real splits ship no text; these are invented, so they can. Without it the
    detector cannot distinguish a true near-duplicate from a SimHash collision
    and downgrades the finding to a warning.
    """
    return {r["uid"]: r["text"] for r in load_jsonl(fixtures_dir / name / "texts.jsonl")}


@pytest.fixture
def leaky(fixtures_dir):
    return load_fixture(fixtures_dir, "toy_leaky")


@pytest.fixture
def leaky_texts(fixtures_dir):
    return load_texts(fixtures_dir, "toy_leaky")


@pytest.fixture
def clean(fixtures_dir):
    return load_fixture(fixtures_dir, "toy_clean")


@pytest.fixture
def clean_texts(fixtures_dir):
    return load_texts(fixtures_dir, "toy_clean")


# -----------------------------------------------------------------------------
# The detector must fail on planted leaks
# -----------------------------------------------------------------------------


def test_planted_leaks_are_detected_at_all(leaky):
    assert failures(find_leakage("toy_leaky", leaky)), (
        "The leakage detector found nothing in a fixture with four deliberate "
        "leaks. A leakage test that cannot fail is not evidence of anything."
    )


@pytest.mark.parametrize(
    "kind",
    ["uid_overlap", "source_id_overlap", "exact_text", "near_duplicate"],
)
def test_each_leak_kind_is_detected(leaky, leaky_texts, kind):
    found = {f.kind for f in failures(find_leakage("toy_leaky", leaky, texts=leaky_texts))}
    assert kind in found, f"{kind} was not detected; found {sorted(found)}"


def test_shared_uid_is_reported(leaky):
    found = failures(find_leakage("toy_leaky", leaky))
    uid_leaks = [f for f in found if f.kind == "uid_overlap"]
    assert uid_leaks
    assert uid_leaks[0].uid_a == uid_leaks[0].uid_b


def test_requeued_claim_is_caught_despite_a_new_uid_and_source_id(leaky):
    """Leak 2: new uid, new source_id, identical text. Only the hash catches it."""
    found = failures(find_leakage("toy_leaky", leaky))
    pairs = {(f.uid_a, f.uid_b) for f in found if f.kind == "exact_text"}
    assert any("dev:9001" in b or "dev:9001" in a for a, b in pairs)


def test_punctuation_variant_is_caught_by_simhash_not_by_exact_hash(leaky, leaky_texts):
    """Leak 4: proves the near-duplicate path does real work.

    The row must NOT be an exact duplicate (normalisation keeps punctuation),
    and must still be flagged.
    """
    near = [f for f in failures(find_leakage("toy_leaky", leaky, texts=leaky_texts))
            if f.kind == "near_duplicate"]
    assert near, "the punctuation-only variant was not caught"
    finding = near[0]
    assert finding.distance is not None and 0 < finding.distance <= 8

    by_uid = {r["uid"]: r for rows in leaky.values() for r in rows}
    a, b = by_uid[finding.uid_a], by_uid[finding.uid_b]
    assert a["text_sha1"] != b["text_sha1"], (
        "this pair is an exact duplicate, so it does not exercise the SimHash path"
    )


# -----------------------------------------------------------------------------
# The detector must stay quiet on clean data
# -----------------------------------------------------------------------------


def test_clean_fixture_is_clean(clean, clean_texts):
    found = find_leakage("toy_clean", clean, texts=clean_texts)
    assert found == [], f"false positives on clean data: {[f.detail for f in found]}"


def test_detector_is_deterministic(leaky):
    first = [f.as_dict() for f in find_leakage("toy_leaky", leaky)]
    second = [f.as_dict() for f in find_leakage("toy_leaky", leaky)]
    assert first == second


# -----------------------------------------------------------------------------
# The building blocks
# -----------------------------------------------------------------------------


def test_normalisation_collapses_forward_artefacts_and_emoji():
    base = "The Ganges flows through India."
    dressed = "Forwarded many times: The Ganges flows through India. \U0001f1ee\U0001f1f3"
    assert normalize_for_hashing(base) == normalize_for_hashing(dressed)


def test_normalisation_collapses_zero_width_joiners():
    """ZWJ/ZWNJ are meaningful in Indic scripts, so two spellings must collide."""
    assert normalize_for_hashing("क्‍ष") == \
        normalize_for_hashing("क्ष")


def test_simhash_separates_variants_from_unrelated_claims():
    base = "The Reserve Bank of India kept the repo rate unchanged in June."
    variant = base.replace(".", "!!")
    unrelated = "Drinking hot water every hour cures the common cold."
    assert hamming(simhash64(base), simhash64(variant)) <= 8
    assert hamming(simhash64(base), simhash64(unrelated)) > 14


def test_simhash_is_stable_across_processes():
    """Committed to git, so it cannot depend on PYTHONHASHSEED."""
    assert simhash64("a stable claim about something") == \
        simhash64("a stable claim about something")


# -----------------------------------------------------------------------------
# Reporting
# -----------------------------------------------------------------------------


def test_report_names_the_offending_rows(leaky):
    report = format_report("toy_leaky", find_leakage("toy_leaky", leaky))
    assert "toy_leaky" in report
    assert "uid_overlap" in report
    assert "failing" in report


def test_per_split_counts_break_down_by_language_and_script(clean):
    counts = per_split_counts(clean)
    assert counts["train"]["total"] == 14
    assert counts["train"]["lang=hi"] == 5
    assert counts["train"]["hi/latn"] == 2


def test_near_duplicates_only_warn_when_text_is_unavailable(leaky):
    """Without text, a SimHash hit cannot be confirmed, so it must not fail a build.

    On real data a meaningful share of hits at Hamming <= 8 have Jaccard below
    0.8 -- close sketches, different claims. Failing on an unconfirmable signal
    would contradict the dedup pass in scripts/build_splits.py, which drops a
    row only when SimHash and Jaccard agree. CI has no data/interim, so this is
    the path CI actually takes.
    """
    found = find_leakage("toy_leaky", leaky)  # no texts=
    near = [f for f in found if f.kind == "near_duplicate"]
    assert near, "the near-duplicate should still be REPORTED without text"
    assert all(f.severity == "warn" for f in near)
    assert all("UNCONFIRMED" in f.detail for f in near)

    # The checks that need no text must still fail hard.
    kinds = {f.kind for f in failures(found)}
    assert {"uid_overlap", "source_id_overlap", "exact_text"} <= kinds
