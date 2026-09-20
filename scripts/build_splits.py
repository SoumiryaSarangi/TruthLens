"""The only sanctioned way to write or re-lock data/splits/.

CLAUDE.md: "NEVER regenerate files in data/splits/. They are frozen and
committed. If a split file seems wrong, stop and ask."

Session 2's dataset loaders call `freeze_split()` from here rather than
writing split files themselves, so the refuse-to-overwrite behaviour cannot be
bypassed by accident.

Overwriting an existing frozen split requires ALL THREE of:

    TRUTHLENS_ALLOW_SPLIT_REWRITE=1
    --i-know-this-regenerates-frozen-splits
    --reason "why this had to happen"

Three, rather than one, because a single flag gets copy-pasted out of a
half-remembered shell history at 2am. The reason is appended to
docs/split-changelog.md, which is the only record that a split ever moved.

CLI:
    python scripts/build_splits.py status    # what exists, and its counts
    python scripts/build_splits.py verify    # splits vs SPLITS.lock
    python scripts/build_splits.py lock      # (re)write SPLITS.lock
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import write_json, write_jsonl  # noqa: E402
from data.leakage import per_split_counts  # noqa: E402
from data.splits import (  # noqa: E402
    LOCK_PATH,
    build_lock,
    discover_splits,
    load_split,
    validate_split_record,
    verify_lock,
)

SPLITS_ROOT = Path("data/splits")
CHANGELOG = Path("docs/split-changelog.md")
REWRITE_ENV = "TRUTHLENS_ALLOW_SPLIT_REWRITE"


class FrozenSplitError(RuntimeError):
    """An attempt to overwrite a frozen split without the full ceremony."""


def freeze_split(
    path: str | Path,
    rows: Sequence[dict[str, Any]],
    *,
    allow_rewrite: bool = False,
    reason: str | None = None,
) -> int:
    """Write a split file, refusing to clobber one that already exists."""
    target = Path(path)
    for i, rec in enumerate(rows, start=1):
        validate_split_record(rec, where=f"{target} (row {i})")

    if target.exists():
        env_ok = os.environ.get(REWRITE_ENV) == "1"
        if not (allow_rewrite and env_ok and reason):
            missing = []
            if not allow_rewrite:
                missing.append("--i-know-this-regenerates-frozen-splits")
            if not env_ok:
                missing.append(f"{REWRITE_ENV}=1")
            if not reason:
                missing.append('--reason "..."')
            raise FrozenSplitError(
                f"{target} already exists and is frozen.\n"
                f"Missing: {', '.join(missing)}.\n\n"
                "Before forcing this, answer the question CLAUDE.md asks: is the split "
                "wrong, or is the code reading it wrong? Regenerating a split "
                "invalidates every number in results/ that was computed against it."
            )
        record_change(target, reason)

    return write_jsonl(target, rows)


def record_change(target: Path, reason: str) -> None:
    """Append to docs/split-changelog.md. The only record a split ever moved."""
    CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
    if not CHANGELOG.exists():
        CHANGELOG.write_text(
            "# Split changelog\n\n"
            "Every regeneration of a frozen split, and why. An entry here means "
            "every results/*.json produced before it against the same split is no "
            "longer comparable.\n",
            encoding="utf-8",
        )
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with CHANGELOG.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {stamp} — {target.as_posix()}\n\n{reason.strip()}\n")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def cmd_status(_args) -> int:
    found = discover_splits(SPLITS_ROOT)
    if not found:
        print(f"No datasets under {SPLITS_ROOT}.")
        print("Frozen splits are built in Session 2 (docs/build-plan.md, Phase 0 step 2).")
        return 0
    for dataset, splits in found.items():
        print(f"\n{dataset}")
        rows = {name: load_split(path) for name, path in splits.items()}
        for name, counts in per_split_counts(rows).items():
            detail = "  ".join(f"{k}={v}" for k, v in counts.items() if "/" in k)
            print(f"  {name:<6} n={counts['total']:<6} {detail}")
    return 0


def cmd_verify(_args) -> int:
    problems = verify_lock(SPLITS_ROOT, LOCK_PATH)
    if problems:
        print("FROZEN SPLITS HAVE DRIFTED:\n")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {SPLITS_ROOT} matches {LOCK_PATH}")
    return 0


def cmd_lock(args) -> int:
    entries = build_lock(SPLITS_ROOT)
    if not entries:
        print(f"No split files under {SPLITS_ROOT}; nothing to lock.")
        return 0
    if LOCK_PATH.exists() and not args.force:
        existing = verify_lock(SPLITS_ROOT, LOCK_PATH)
        if existing:
            print("Refusing to overwrite SPLITS.lock while the splits disagree with it:\n")
            for p in existing:
                print(f"  - {p}")
            print("\nThis is the situation the lock exists to catch. Re-locking would "
                  "erase the evidence. Pass --force only if you have decided the new "
                  "bytes are correct.")
            return 1
    write_json(LOCK_PATH, {"version": 1, "files": entries})
    print(f"Locked {len(entries)} split file(s) into {LOCK_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_splits.py",
                                     description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show datasets and per-language counts")
    sub.add_parser("verify", help="check splits against SPLITS.lock")
    lock = sub.add_parser("lock", help="(re)write SPLITS.lock")
    lock.add_argument("--force", action="store_true",
                      help="re-lock even though the splits disagree with the current lock")

    args = parser.parse_args(argv)
    return {"status": cmd_status, "verify": cmd_verify, "lock": cmd_lock}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
