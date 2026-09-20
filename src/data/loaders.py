"""Dataset loaders. Every source becomes the same record shape.

Each loader yields the split-manifest record defined in src/data/splits.py:
identifiers, language, detected script, hashes. Source TEXT is returned
separately, by `materialize`, and written to the gitignored data/interim/ --
never into a committed split file. See data/CLAUDE.md for why.

Adding a dataset means adding a loader here and a registry entry. Nothing
else in the pipeline should know which dataset a row came from.
"""

from __future__ import annotations

import ast
import csv
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

from common.hashing import sha1_text
from common.io_jsonl import load_json
from data.labels import map_averitec_label
from data.normalize import normalize_for_hashing
from data.script_id import detect_script, script_purity
from data.simhash import simhash_hex

RAW = Path("data/raw")

# X-CLAIM's own splits, which we keep as-is.
XCLAIM_LANGS = ("en", "hi", "pa")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


class Row(NamedTuple):
    """A loaded example: the manifest record, plus the text that stays local."""

    record: dict[str, Any]
    text: str


def _make_record(
    *,
    dataset: str,
    split: str,
    index: int,
    lang: str,
    text: str,
    source_id: str,
    label: str | None,
    label_set: str | None,
) -> dict[str, Any]:
    script = detect_script(text)
    normalised = normalize_for_hashing(text)
    record: dict[str, Any] = {
        "uid": f"{dataset}:{lang}:{split}:{index:05d}",
        "dataset": dataset,
        "split": split,
        "lang": lang,
        "script": script,
        "source_id": source_id,
        "text_sha1": sha1_text(normalised),
        "simhash64": simhash_hex(text),
        "n_chars": len(text),
    }
    if label is not None:
        record["label"] = label
        record["label_set"] = label_set
    return record


# -----------------------------------------------------------------------------
# AVeriTeC
# -----------------------------------------------------------------------------


def load_averitec(split_file: str, split_name: str) -> Iterator[Row]:
    """Load AVeriTeC train.json or dev.json.

    AVeriTeC ships no per-claim identifier, so the record's position in the
    file IS its identity. That is only safe because the file's sha256 is
    recorded in data/raw/DOWNLOADS.json and in the split MANIFEST: if upstream
    re-releases with a different ordering, the hash changes and the mismatch
    is visible rather than silent.
    """
    path = RAW / "averitec" / split_file
    records = load_json(path)
    for i, item in enumerate(records):
        claim = (item.get("claim") or "").strip()
        if not claim:
            continue
        yield Row(
            record=_make_record(
                dataset="averitec",
                split=split_name,
                index=i,
                lang="en",
                text=claim,
                source_id=f"averitec:{split_file}:{i}",
                label=map_averitec_label(item["label"]),
                label_set="verdict_5class",
            ),
            text=claim,
        )


# -----------------------------------------------------------------------------
# X-CLAIM
# -----------------------------------------------------------------------------


def _join_tokens(raw: str) -> str:
    """X-CLAIM stores a Python list literal in the `tokens` column."""
    try:
        tokens = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw.strip()
    if isinstance(tokens, list):
        return " ".join(str(t) for t in tokens).strip()
    return str(tokens).strip()


def load_xclaim(lang: str, split_name: str) -> Iterator[Row]:
    """Load one X-CLAIM language/split CSV.

    This is a span-identification dataset: the columns are the post's tokens
    and the start/end indices of the claim span. There is no verdict label, so
    the manifest record carries none -- `label` is optional by design.
    """
    path = RAW / "x_claim" / f"{split_name}-{lang}.csv"
    with path.open("r", encoding="utf-8", newline="") as fh:
        for i, item in enumerate(csv.DictReader(fh)):
            text = _join_tokens(item.get("tokens", ""))
            if not text:
                continue
            yield Row(
                record=_make_record(
                    dataset="x_claim",
                    split=split_name,
                    index=i,
                    lang=lang,
                    text=text,
                    source_id=f"x_claim:{split_name}-{lang}:{i}",
                    label=None,
                    label_set=None,
                ),
                text=text,
            )


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------


def averitec_rows() -> dict[str, list[Row]]:
    """AVeriTeC's public release: train and dev only.

    The test split is withheld for the FEVER shared task. Carving a local test
    set out of train is handled by scripts/build_splits.py, not here, so the
    loader stays a faithful reading of what upstream actually published.
    """
    return {
        "train": list(load_averitec("train.json", "train")),
        "dev": list(load_averitec("dev.json", "dev")),
    }


def xclaim_rows() -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    for split in out:
        for lang in XCLAIM_LANGS:
            out[split].extend(load_xclaim(lang, split))
    return out


LOADERS = {
    "averitec": averitec_rows,
    "x_claim": xclaim_rows,
}


def code_mixed_share(rows: list[Row], threshold: float = 0.9) -> float:
    """Share of rows whose dominant script covers less than `threshold`.

    Reported in docs/data-profile.md because code-mixing is the normal case
    for forwards, and a single `script` label hides it.
    """
    if not rows:
        return 0.0
    mixed = sum(1 for r in rows if script_purity(r.text) < threshold)
    return mixed / len(rows)
