"""Shared test fixtures.

Every test runs with the repo root as the working directory, because the
harness resolves configs/, data/splits/ and results/ relative to it, exactly
as `make eval` does.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def no_test_split_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the test-split guard is armed, whatever the ambient environment."""
    monkeypatch.delenv("TRUTHLENS_ALLOW_TEST", raising=False)


@pytest.fixture
def allow_test_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUTHLENS_ALLOW_TEST", "1")


def pytest_report_header(config: pytest.Config) -> list[str]:
    allow = os.environ.get("TRUTHLENS_ALLOW_TEST")
    if allow == "1":
        return ["WARNING: TRUTHLENS_ALLOW_TEST=1 is set in this shell -- "
                "the test-split guard is disarmed outside of tests that arm it."]
    return []
