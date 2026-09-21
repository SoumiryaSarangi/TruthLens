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


@pytest.mark.parametrize("dataset", ["averitec", "x_claim", "multiclaim"])
def test_declared_sources_live_under_gitignored_raw(dataset):
    """Source data must never be inside a committed directory."""
    for path in loaders.LOADER_SOURCES[dataset]:
        assert Path(path).as_posix().startswith("data/raw/")
