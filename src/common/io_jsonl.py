"""JSONL read/write.

One reader and one writer, both strict. Silent tolerance for a malformed line
is exactly how a partially-parsed predictions file turns into a wrong number.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


class JsonlError(ValueError):
    """Raised with the file and line number, so the message is actionable."""


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield one dict per line. Blank lines are an error, not a shrug."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                raise JsonlError(f"{p}:{lineno}: blank line in JSONL")
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise JsonlError(f"{p}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise JsonlError(f"{p}:{lineno}: expected a JSON object, got {type(obj).__name__}")
            yield obj


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return list(read_jsonl(path))


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    """Atomically write rows with sorted keys and LF endings.

    Sorted keys and explicit newline="\n" are what make a split file's sha256
    reproducible across Windows and CI. Atomic replace means an interrupted
    write can never leave a half-written frozen split on disk.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")))
                fh.write("\n")
                n += 1
        Path(tmp).replace(p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return n


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> None:
    """Atomically write a JSON document (results, manifests, the splits lock)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, sort_keys=True, ensure_ascii=False, indent=indent)
            fh.write("\n")
        Path(tmp).replace(p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)
