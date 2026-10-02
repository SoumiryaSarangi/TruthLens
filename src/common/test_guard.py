"""The test-split lock, in one place (CLAUDE.md; NFR-6).

`evaluate.py` refuses to SCORE a test split without TRUTHLENS_ALLOW_TEST=1. That
alone leaves a hole: test PREDICTIONS could be written, inspected and iterated
on, and only the final scoring would ever ask. Every entry point that runs a
model over a split calls this too, so looking at test needs the same flag as
scoring it.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ENV = "TRUTHLENS_ALLOW_TEST"


class TestSplitLocked(RuntimeError):
    """A test split was opened without TRUTHLENS_ALLOW_TEST=1."""

    __test__ = False      # not a pytest test class, whatever its name says


def uid_split(uid: str) -> str | None:
    """The split field of a uid like `averitec:en:test:00000`, if it has one."""
    parts = uid.split(":")
    return parts[2] if len(parts) >= 4 else None


def is_test(split_path: Path | None, rows: Iterable[dict[str, Any]]) -> bool:
    """A file named test.*, or any row whose `split` (or uid) says test."""
    if split_path is not None and Path(split_path).stem == "test":
        return True
    return any(r.get("split") == "test" or uid_split(str(r.get("uid", ""))) == "test"
               for r in rows)


def allowed() -> bool:
    return os.environ.get(ENV) == "1"


def require_allowed(split_path: Path | None, rows: Iterable[dict[str, Any]],
                    what: str = "this run") -> None:
    if is_test(split_path, list(rows)) and not allowed():
        where = split_path if split_path is not None else "the input"
        raise TestSplitLocked(
            f"{where} is a TEST split, and {what} would look at it.\n"
            "The test set is for the final reported number, not for model selection. "
            "Every time it is looked at, it becomes a little less of a test set.\n"
            f"If this really is the final run, set {ENV}=1 and say so in the "
            "config's `notes:`."
        )
