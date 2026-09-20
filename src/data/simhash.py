"""64-bit SimHash over character 5-grams, for near-duplicate detection.

Why this exists: data/splits/*.jsonl are ID manifests and carry no text, so a
leakage test running in CI has nothing to compare. A SimHash is 16 hex
characters, travels inside the committed manifest, redistributes no source
text, and still answers "are these two claims nearly the same?".

The digest is blake2b, not Python's `hash()`, because the value is committed to
git and must be identical on every machine and every interpreter run.

Layered with the exact `text_sha1` check in src/data/leakage.py:
  text_sha1 equal                -> certain duplicate
  Hamming(simhash) <= threshold  -> probable near-duplicate, worth a human look
  materialised text available    -> exact Jaccard confirms or clears the pair
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator

from data.normalize import char_shingles

BITS = 64
_BAND_BITS = 16
_N_BANDS = BITS // _BAND_BITS  # 4 bands of 16 bits


def _feature_hash(shingle: str) -> int:
    return int.from_bytes(hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest(), "big")


def simhash64(text: str, k: int = 5) -> int:
    """SimHash of the normalised text. Returns 0 for text too short to shingle."""
    shingles = char_shingles(text, k)
    if not shingles:
        return 0
    counters = [0] * BITS
    for sh in shingles:
        h = _feature_hash(sh)
        for bit in range(BITS):
            counters[bit] += 1 if (h >> bit) & 1 else -1
    out = 0
    for bit in range(BITS):
        if counters[bit] > 0:
            out |= 1 << bit
    return out


def simhash_hex(text: str, k: int = 5) -> str:
    """The form stored in a split record: zero-padded 16-char hex."""
    return f"{simhash64(text, k):016x}"


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def candidate_pairs(
    items_a: list[tuple[str, int]],
    items_b: list[tuple[str, int]],
) -> Iterator[tuple[str, str]]:
    """Pairs across two collections that could be within Hamming distance 3.

    Pigeonhole: if two 64-bit values differ in at most 3 bits, then across 4
    disjoint 16-bit bands at least one band must be identical. Indexing by band
    turns an O(n*m) scan into something that finishes on MultiClaim-sized data.

    Over-generates by design -- the caller checks true Hamming distance.
    """
    index: list[dict[int, list[str]]] = [{} for _ in range(_N_BANDS)]
    for key, h in items_a:
        for band in range(_N_BANDS):
            chunk = (h >> (band * _BAND_BITS)) & 0xFFFF
            index[band].setdefault(chunk, []).append(key)

    emitted: set[tuple[str, str]] = set()
    for key_b, h in items_b:
        for band in range(_N_BANDS):
            chunk = (h >> (band * _BAND_BITS)) & 0xFFFF
            for key_a in index[band].get(chunk, ()):
                pair = (key_a, key_b)
                if pair not in emitted:
                    emitted.add(pair)
                    yield pair


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Exact Jaccard over shingle sets. Used only to confirm flagged pairs."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = len(sa | sb)
    return len(sa & sb) / union if union else 0.0
