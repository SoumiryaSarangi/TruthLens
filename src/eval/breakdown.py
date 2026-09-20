"""Per-language and per-script slicing.

CLAUDE.md: "All metrics reported per-language AND per-script (native vs
romanized)." That is not a reporting nicety here, it is the research
contribution: the gap between the native and romanized columns is the finding.
So the breakdown is built into the harness rather than being something a
notebook does afterwards.

Small cells are marked, never hidden. Punjabi dev is 100 examples and X-CLAIM
Punjabi train is 346, so low-n cells are guaranteed. A reader needs to see the
number *and* that it rests on 27 examples.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

MIN_CELL_N = 30

# Fields a config may slice on. Restricted on purpose: an arbitrary field would
# let one experiment report cells another cannot, and the ablation tables stop
# lining up.
ALLOWED_KEYS: tuple[str, ...] = ("lang", "script", "dataset", "split")


def cell_key(record: dict[str, Any], keys: Sequence[str]) -> str:
    """Stable, readable cell name: 'lang=hi,script=latn'."""
    return ",".join(f"{k}={record.get(k, 'NA')}" for k in keys)


def validate_keys(keys: Sequence[str]) -> None:
    unknown = [k for k in keys if k not in ALLOWED_KEYS]
    if unknown:
        raise ValueError(
            f"breakdown key(s) {unknown} not allowed; choose from {list(ALLOWED_KEYS)}"
        )


def group_indices(
    records: Sequence[dict[str, Any]], keys: Sequence[str],
) -> dict[str, list[int]]:
    """Map cell name -> indices of the records in it.

    Indices rather than records, so the caller can slice its own parallel
    arrays (gold, predictions) with the same grouping and cannot get them out
    of alignment.
    """
    validate_keys(keys)
    groups: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        groups.setdefault(cell_key(rec, keys), []).append(i)
    return dict(sorted(groups.items()))


def compute_with_breakdown(
    records: Sequence[dict[str, Any]],
    keys: Sequence[str],
    compute: Callable[[Sequence[int]], dict[str, Any]],
    *,
    min_cell_n: int = MIN_CELL_N,
) -> dict[str, Any]:
    """Run `compute` over all records and over each cell.

    `compute` takes indices into `records` and returns a metrics dict. Every
    cell result gains `n` and, where warranted, `low_n: true`.
    """
    all_indices = list(range(len(records)))
    out: dict[str, Any] = {"overall": compute(all_indices), "by": {}}
    if not keys:
        return out

    for name, idx in group_indices(records, keys).items():
        cell = compute(idx)
        cell["n"] = float(len(idx))
        if len(idx) < min_cell_n:
            cell["low_n"] = True
            cell["low_n_threshold"] = float(min_cell_n)
        out["by"][name] = cell
    return out


def script_gap(by_cell: dict[str, Any], metric: str) -> dict[str, Any]:
    """Native-vs-romanized gap per language: the headline comparison.

    Returns {lang: {native, romanized, gap}} where gap = native - romanized.
    A positive gap is the romanization penalty this project exists to quantify.
    """
    native_scripts = {"deva", "guru"}
    per_lang: dict[str, dict[str, Any]] = {}

    for name, cell in by_cell.items():
        parts = dict(p.split("=", 1) for p in name.split(",") if "=" in p)
        lang, script = parts.get("lang"), parts.get("script")
        if lang is None or script is None or metric not in cell:
            continue
        slot = "native" if script in native_scripts else "romanized"
        entry = per_lang.setdefault(lang, {})
        # English has no native/romanized distinction; it is latn either way.
        if lang == "en":
            entry["native"] = cell[metric]
        else:
            entry[slot] = cell[metric]
        entry[f"n_{slot}" if lang != "en" else "n_native"] = cell.get("n")

    for lang, entry in per_lang.items():
        if "native" in entry and "romanized" in entry:
            entry["gap"] = entry["native"] - entry["romanized"]
        per_lang[lang] = dict(sorted(entry.items()))
    return dict(sorted(per_lang.items()))
