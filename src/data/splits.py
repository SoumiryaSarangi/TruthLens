"""The frozen-splits contract: record shape, discovery, and lock verification.

data/splits/ is the foundation every number in this project stands on.
CLAUDE.md: "NEVER regenerate files in data/splits/. They are frozen and
committed." This module is how that rule is checked rather than merely stated.

A split file is an ID MANIFEST, not text. It carries identifiers, metadata and
a hash of the normalised text -- never the text itself. That keeps the repo
publishable without redistributing AVeriTeC, X-CLAIM or the access-restricted
MultiClaim corpus, while still letting tests/test_no_leakage.py detect a claim
appearing in two splits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.hashing import count_lines, sha256_file
from common.io_jsonl import load_json, load_jsonl, write_json

SPLIT_NAMES: tuple[str, ...] = ("train", "dev", "test")
LANGS: tuple[str, ...] = ("en", "hi", "pa")
SCRIPTS: tuple[str, ...] = ("deva", "guru", "latn")

REQUIRED_FIELDS: tuple[str, ...] = (
    "uid", "dataset", "split", "lang", "script", "source_id",
    "text_sha1",   # exact-duplicate detection
    "simhash64",   # near-duplicate detection, 16 hex chars (src/data/simhash.py)
    "n_chars",
)
OPTIONAL_FIELDS: tuple[str, ...] = ("label", "label_set", "notes")

LOCK_PATH = Path("data/splits/SPLITS.lock")


class SplitError(ValueError):
    """A frozen split violated its contract."""


class SplitLockError(SplitError):
    """A split file's bytes do not match SPLITS.lock."""


def validate_split_record(rec: dict[str, Any], *, where: str) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in rec]
    if missing:
        raise SplitError(f"{where}: split record missing required field(s) {missing}")
    if rec["split"] not in SPLIT_NAMES:
        raise SplitError(f"{where}: split={rec['split']!r}, expected one of {SPLIT_NAMES}")
    if rec["lang"] not in LANGS:
        raise SplitError(f"{where}: lang={rec['lang']!r}, expected one of {LANGS}")
    if rec["script"] not in SCRIPTS:
        raise SplitError(f"{where}: script={rec['script']!r}, expected one of {SCRIPTS}")
    if not isinstance(rec["text_sha1"], str) or len(rec["text_sha1"]) != 40:
        raise SplitError(f"{where}: text_sha1 must be a 40-char sha1 hex digest")
    if not isinstance(rec["simhash64"], str) or not re.fullmatch(r"[0-9a-f]{16}", rec["simhash64"]):
        raise SplitError(f"{where}: simhash64 must be 16 lowercase hex chars")
    unknown = sorted(set(rec) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if unknown:
        raise SplitError(
            f"{where}: unexpected field(s) {unknown}. Extend REQUIRED/OPTIONAL_FIELDS in "
            "src/data/splits.py deliberately -- an ad-hoc field in one dataset's splits "
            "and not another's is how per-language breakdowns start disagreeing."
        )


def load_split(path: str | Path) -> list[dict[str, Any]]:
    """Load and fully validate one split file, including uid uniqueness."""
    p = Path(path)
    rows = load_jsonl(p)
    seen: set[str] = set()
    for i, rec in enumerate(rows, start=1):
        validate_split_record(rec, where=f"{p}:{i}")
        uid = rec["uid"]
        if uid in seen:
            raise SplitError(f"{p}:{i}: duplicate uid {uid!r} within a single split file")
        seen.add(uid)
    return rows


def discover_splits(root: str | Path = "data/splits") -> dict[str, dict[str, Path]]:
    """Map dataset -> {split_name: path} for whatever exists on disk.

    Returns {} when no splits have been built yet, which is the true state at
    the end of Phase 0. Callers skip rather than fail on an empty result.
    """
    r = Path(root)
    found: dict[str, dict[str, Path]] = {}
    if not r.is_dir():
        return found
    for ds_dir in sorted(p for p in r.iterdir() if p.is_dir()):
        files = {n: ds_dir / f"{n}.jsonl" for n in SPLIT_NAMES}
        present = {n: p for n, p in files.items() if p.is_file()}
        if present:
            found[ds_dir.name] = present
    return found


# -----------------------------------------------------------------------------
# SPLITS.lock
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class LockEntry:
    sha256: str
    n_lines: int


def build_lock(root: str | Path = "data/splits") -> dict[str, dict[str, Any]]:
    """Hash every split file under root.

    Keys are POSIX paths RELATIVE TO the lock's own directory, e.g.
    "averitec/dev.jsonl". Relative rather than absolute so the lock verifies
    identically on a laptop, in CI, and in a fresh clone at any path.
    """
    r = Path(root).resolve()
    entries: dict[str, dict[str, Any]] = {}
    for _dataset, splits in discover_splits(r).items():
        for _name, path in splits.items():
            key = path.resolve().relative_to(r).as_posix()
            entries[key] = {"sha256": sha256_file(path), "n_lines": count_lines(path)}
    return entries


def write_lock(entries: dict[str, dict[str, Any]], path: str | Path = LOCK_PATH) -> None:
    write_json(path, {"version": 1, "files": entries})


def read_lock(path: str | Path = LOCK_PATH) -> dict[str, LockEntry]:
    doc = load_json(path)
    return {k: LockEntry(v["sha256"], v["n_lines"]) for k, v in doc["files"].items()}


def verify_lock(root: str | Path = "data/splits",
                lock_path: str | Path = LOCK_PATH) -> list[str]:
    """Return a list of human-readable problems; empty means the splits are intact."""
    root = Path(root)
    lock_file = Path(lock_path)
    on_disk = build_lock(root)

    if not on_disk and not lock_file.is_file():
        return []  # nothing built yet: legitimate at the end of Phase 0

    if not lock_file.is_file():
        return [
            f"{len(on_disk)} split file(s) exist under {root} but {lock_file} is missing. "
            "Frozen splits without a lock cannot be verified. Run `make lock`."
        ]

    locked = read_lock(lock_file)
    problems: list[str] = []
    for key in sorted(set(locked) | set(on_disk)):
        if key not in on_disk:
            problems.append(
                f"{key}: in {lock_file} but MISSING from disk (was it deleted?)"
            )
        elif key not in locked:
            problems.append(
                f"{key}: on disk but NOT in SPLITS.lock (a split was added without locking it)"
            )
        elif on_disk[key]["sha256"] != locked[key].sha256:
            problems.append(
                f"{key}: sha256 MISMATCH -- a frozen split has been modified.\n"
                f"    locked: {locked[key].sha256}\n"
                f"    ondisk: {on_disk[key]['sha256']}\n"
                "    CLAUDE.md: frozen splits are never regenerated. If this is "
                "intentional, it must go through scripts/build_splits.py and be "
                "recorded in docs/split-changelog.md."
            )
        elif on_disk[key]["n_lines"] != locked[key].n_lines:
            problems.append(
                f"{key}: line count changed {locked[key].n_lines} -> {on_disk[key]['n_lines']}"
            )
    return problems
