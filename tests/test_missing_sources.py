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


def test_dedup_survives_an_eval_split_whose_text_is_not_readable():
    """The CI condition: split ids committed, source text absent.

    MultiClaim is access-restricted. Its split files are committed, so another
    dataset's build sees its uids and SimHash values, but `data/interim/multiclaim/`
    does not exist on a runner -- so a near-duplicate candidate against it cannot
    be confirmed by Jaccard. This used to raise KeyError and fail the whole
    reproducibility job.

    Skipping the pair is right rather than merely convenient: the exact-hash
    check still catches identical text, so what is lost is near-duplicate
    detection against data the runner is not allowed to read, and the build says
    so instead of pretending it checked.
    """
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "build_splits", Path("scripts/build_splits.py")
    )
    build_splits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_splits)

    def row(uid, text, simhash):
        return loaders.Row(
            record={"uid": uid, "dataset": "toy", "split": "train", "lang": "en",
                    "script": "latn", "source_id": uid,
                    "text_sha1": "a" * 40, "simhash64": simhash, "n_chars": len(text)},
            text=text,
        )

    rows = {"train": [row("toy:en:train:00000", "a claim about vaccines", "0000000000000000")]}
    # An external eval row with an identical SimHash -- so it IS a candidate --
    # but no text on hand to confirm it with.
    external = {
        "hashes": set(),
        "items": [("multiclaim:en:test:00352", 0)],
        "texts": {},
    }
    kept, report = build_splits.deduplicate(rows, external_eval=external)
    assert len(kept["train"]) == 1, "an unconfirmable candidate must not be dropped"
    assert report["near_duplicate_candidates_unverifiable_no_text"] == 1
