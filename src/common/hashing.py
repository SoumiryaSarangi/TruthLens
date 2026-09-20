"""Content addressing.

Every claim about "this result came from this data" in results/*.json rests on
these functions, so they are deliberately boring and have no options: one
canonical way to hash a file, a string and a config.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    """Hash a file's raw bytes. Binary mode, so line endings are part of the hash."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha1_text(text: str) -> str:
    """SHA-1 of a UTF-8 string.

    Used only for `text_sha1` in the frozen splits, where the input is already
    normalised by data.normalize.normalize_for_hashing. SHA-1 is fine here: this
    is duplicate detection, not security, and it keeps split files smaller.
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, no insignificant whitespace.

    Two configs that differ only in key order must hash identically, or the
    same experiment silently produces two different config_hash values.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj))


def count_lines(path: str | Path) -> int:
    """Number of newline-terminated lines, counted on raw bytes."""
    n = 0
    with Path(path).open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            n += chunk.count(b"\n")
    return n
