"""A dataset whose source data is absent must be skipped, not crash the build.

MultiClaim is access-restricted and can never exist in CI, so the
reproducibility job has to verify the datasets it CAN fetch and report the rest
as unverifiable. It must not fail -- and, just as importantly, must not quietly
pass as though everything were checked.

This is regression cover: CI went red on exactly this the first time MultiClaim
splits were committed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from data import loaders


def test_sources_available_is_true_when_files_exist(tmp_path, monkeypatch):
    present = tmp_path / "present.csv"
    present.write_text("x", encoding="utf-8")
    monkeypatch.setitem(loaders.LOADER_SOURCES, "fake", (present,))
    assert loaders.sources_available("fake") is True
    assert loaders.missing_sources("fake") == []


def test_sources_available_is_false_when_a_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setitem(loaders.LOADER_SOURCES, "fake",
                        (tmp_path / "nope.csv", tmp_path / "also-nope.csv"))
    assert loaders.sources_available("fake") is False
    assert len(loaders.missing_sources("fake")) == 2


def test_every_registered_loader_declares_its_sources():
    """A loader with no declared source would silently look 'available'."""
    assert set(loaders.LOADERS) <= set(loaders.LOADER_SOURCES)


def test_multiclaim_sources_are_declared_and_restricted():
    """MultiClaim is the reason this exists; its CSVs must be declared."""
    declared = [p.as_posix() for p in loaders.LOADER_SOURCES["multiclaim"]]
    assert any("posts.csv" in p for p in declared)
    assert all(p.startswith("data/raw/") for p in declared)


def test_handtyped_sources_are_declared_and_unpublishable():
    """The hand-typed forwards are people's own writing.

    They were collected for this project and are not a public dataset, so they
    are in exactly the same position as MultiClaim: they cannot be committed,
    cannot reach CI, and the build must skip them rather than fail.
    """
    declared = [p.as_posix() for p in loaders.LOADER_SOURCES["handtyped"]]
    assert declared == ["data/raw/handtyped/forwards.csv"]


@pytest.mark.parametrize("dataset", ["averitec", "x_claim", "multiclaim", "handtyped"])
def test_declared_sources_live_under_gitignored_raw(dataset):
    """Source data must never be inside a committed directory."""
    for path in loaders.LOADER_SOURCES[dataset]:
        assert Path(path).as_posix().startswith("data/raw/")


def test_cross_dataset_dedup_is_exact_match_only():
    """A public split must be rebuildable from public data.

    Confirming a near-duplicate needs the text on both sides, and a committed
    split carries ids and hashes, not text. MultiClaim's text can never exist on
    a CI runner, so letting near-duplicates decide cross-dataset drops made
    x_claim/train's CONTENT depend on data CI cannot read -- the same build gave
    4,398 rows locally and 4,446 on the runner, and the reproducibility job
    caught it.

    So the cross-dataset rule is exact match, which reproduces everywhere.
    A SimHash-identical external row must NOT drop a train row; an exact hash
    match must.
    """
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "build_splits", Path("scripts/build_splits.py")
    )
    build_splits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_splits)

    def row(uid, text, sha, simhash):
        return loaders.Row(
            record={"uid": uid, "dataset": "toy", "split": "train", "lang": "en",
                    "script": "latn", "source_id": uid,
                    "text_sha1": sha, "simhash64": simhash, "n_chars": len(text)},
            text=text,
        )

    rows = {"train": [row("toy:en:train:00000", "a claim about vaccines",
                          "a" * 40, "0000000000000000")]}

    # Same SimHash as a restricted dataset's eval row, and no text to confirm
    # it with. Must be kept: dropping it would make this split unreproducible
    # wherever that text is absent.
    near_only = {"hashes": set(), "items": [("multiclaim:en:test:00352", 0)], "texts": {}}
    kept, report = build_splits.deduplicate(rows, external_eval=near_only)
    assert len(kept["train"]) == 1, (
        "a cross-dataset NEAR duplicate must not be dropped -- it cannot be "
        "reproduced where the other dataset's text is unavailable"
    )
    assert report["dropped_from_train"]["in_another_dataset_eval_split"] == 0

    # An EXACT hash match is in the committed split file, so it reproduces
    # everywhere and must drop the row.
    exact = {"hashes": {"a" * 40}, "items": [], "texts": {}}
    kept, report = build_splits.deduplicate(rows, external_eval=exact)
    assert kept["train"] == []
    assert report["dropped_from_train"]["in_another_dataset_eval_split"] == 1
