"""Verifies that no frozen split has changed since it was locked.

CLAUDE.md: "NEVER regenerate files in data/splits/. They are frozen and
committed. If a split file seems wrong, stop and ask."

SPLITS.lock records the sha256 and line count of every split file. This test
recomputes them. It covers both the real splits under data/splits/ and the
fixtures under tests/fixtures/, so the freeze machinery is exercised on every
run rather than only once real data exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from common.hashing import sha256_file
from data.splits import LOCK_PATH, build_lock, discover_splits, read_lock, verify_lock

SPLITS_ROOT = Path("data/splits")
FIXTURES_ROOT = Path("tests/fixtures")
FIXTURES_LOCK = FIXTURES_ROOT / "SPLITS.lock"

pytestmark = pytest.mark.leakage


def test_real_splits_match_their_lock():
    problems = verify_lock(SPLITS_ROOT, LOCK_PATH)
    assert not problems, "\n".join(["Frozen splits have drifted from SPLITS.lock:", *problems])


def test_fixture_splits_match_their_lock():
    """The same check, on data that exists today, so the code path is live."""
    problems = verify_lock(FIXTURES_ROOT, FIXTURES_LOCK)
    assert not problems, "\n".join(["Fixture splits have drifted:", *problems])


def test_lock_covers_every_split_on_disk():
    if not discover_splits(SPLITS_ROOT):
        pytest.skip(f"no datasets under {SPLITS_ROOT} yet")
    locked = set(read_lock(LOCK_PATH))
    on_disk = set(build_lock(SPLITS_ROOT))
    assert on_disk <= locked, f"unlocked split file(s): {sorted(on_disk - locked)}"


def test_tampering_with_a_split_is_detected(tmp_path: Path):
    """Proves the freeze check can fail, not merely that it currently passes.

    Copies the fixtures, appends a single byte to one split, and asserts the
    verifier notices. Without this, a permanently-green freeze test could just
    mean the hashes are never actually compared.
    """
    import shutil

    work = tmp_path / "fixtures"
    shutil.copytree(FIXTURES_ROOT, work)
    assert verify_lock(work, work / "SPLITS.lock") == [], "copy should start clean"

    victim = work / "toy_clean" / "dev.jsonl"
    before = sha256_file(victim)
    with victim.open("ab") as fh:
        fh.write(b"\n")

    problems = verify_lock(work, work / "SPLITS.lock")
    assert problems, "appending a byte to a frozen split went undetected"
    assert any("MISMATCH" in p or "line count" in p for p in problems)
    assert before != sha256_file(victim)


def test_missing_lock_with_splits_present_is_an_error(tmp_path: Path):
    import shutil

    work = tmp_path / "fixtures"
    shutil.copytree(FIXTURES_ROOT, work)
    (work / "SPLITS.lock").unlink()

    problems = verify_lock(work, work / "SPLITS.lock")
    assert problems and "missing" in problems[0].lower()


def test_empty_splits_directory_is_not_an_error(tmp_path: Path):
    """True state at the end of Phase 0: nothing built, nothing to verify."""
    assert verify_lock(tmp_path, tmp_path / "SPLITS.lock") == []
