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
from common.seeds import SEED
from data.labels import map_averitec_label
from data.normalize import char_shingles, normalize_for_hashing
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


# -----------------------------------------------------------------------------
# MultiClaim / SemEval-2025 Task 7
# -----------------------------------------------------------------------------


MULTICLAIM_SPLIT_FRACTIONS = {"train": 0.8, "dev": 0.1, "test": 0.1}


def load_multiclaim(langs: tuple[str, ...] = ("en", "hi", "pa")) -> dict[str, list[Row]]:
    """Posts as retrieval queries, split 80/10/10 stratified by language.

    MultiClaim ships no official split, so one is made here and frozen like any
    other. Stratifying by language matters more than usual: Punjabi has only 91
    posts in the entire corpus, and an unstratified random split could leave a
    test set with almost none.

    Only posts that have at least one annotated fact-check are kept. A post with
    no pair has no gold, cannot be scored, and would silently vanish from the
    denominator.
    """
    import random

    from data.multiclaim import load_pairs, load_posts

    posts = load_posts(langs=set(langs))
    paired: dict[str, list[str]] = {}
    for post_id, fc_id, _rel in load_pairs():
        if post_id in posts:
            paired.setdefault(post_id, []).append(fc_id)

    # Deduplicate BEFORE splitting, not after.
    #
    # MultiClaim ships no official splits, so these are ours -- which means a
    # duplicated post appearing in both dev and test is a bug in this function,
    # not upstream leakage to be allowlisted. The allowlist in
    # data/splits/KNOWN_LEAKAGE.json exists for overlap we cannot fix without
    # altering a published benchmark; this we can fix, so we do.
    #
    # Measured before this: 13 posts appeared in both dev and test. Keeping the
    # lowest post_id makes the choice deterministic rather than dependent on
    # CSV order.
    # Exact duplicates first, then NEAR duplicates. Exact alone is not enough:
    # the same viral post gets reposted with an emoji changed or a URL dropped,
    # which normalises to different text but is plainly the same item. Measured
    # after exact-only dedup: 30 near-duplicate pairs still straddled splits,
    # at Jaccard 0.92-0.97.
    seen: dict[str, str] = {}
    for post_id in sorted(paired, key=lambda x: (len(x), x)):
        key = normalize_for_hashing(posts[post_id].text)
        seen.setdefault(key, post_id)
    unique_ids = _drop_near_duplicates(
        {pid: posts[pid].text for pid in seen.values()}
    )

    by_lang: dict[str, list[str]] = {}
    for post_id in sorted(paired):
        if post_id not in unique_ids:
            continue
        by_lang.setdefault(posts[post_id].lang or "en", []).append(post_id)

    out: dict[str, list[Row]] = {"train": [], "dev": [], "test": []}
    rng = random.Random(SEED)
    for lang in sorted(by_lang):
        ids = sorted(by_lang[lang])
        rng.shuffle(ids)
        n = len(ids)
        n_train = int(n * MULTICLAIM_SPLIT_FRACTIONS["train"])
        n_dev = int(n * MULTICLAIM_SPLIT_FRACTIONS["dev"])
        chunks = {"train": ids[:n_train],
                  "dev": ids[n_train:n_train + n_dev],
                  "test": ids[n_train + n_dev:]}
        for split, chunk in chunks.items():
            for i, post_id in enumerate(chunk):
                text = posts[post_id].text
                out[split].append(Row(
                    record=_make_record(
                        dataset="multiclaim", split=split, index=i, lang=lang,
                        text=text, source_id=f"multiclaim:post:{post_id}",
                        label=None, label_set=None,
                    ),
                    text=text,
                ))
    return out


def _drop_near_duplicates(texts: dict[str, str]) -> set[str]:
    """Keep one representative per near-duplicate cluster.

    Reuses the same signals and thresholds as the split-building dedup pass in
    scripts/build_splits.py -- SimHash proximity confirmed by exact Jaccard --
    so "near duplicate" means one thing across the project.

    Union-find over candidate pairs rather than an all-pairs comparison: 32k
    posts would be half a billion comparisons, while the banded SimHash index
    only proposes plausible ones.
    """
    from data.leakage import FAIL_JACCARD, WARN_HAMMING
    from data.simhash import candidate_pairs, hamming, jaccard, simhash64

    # Thresholds are IMPORTED from the detector, never redeclared. They drifted
    # once already: this clustered at Hamming <= 8 while tests/test_no_leakage
    # failed anything with Jaccard >= 0.90 out to Hamming 14, leaving a band the
    # clusterer never considered and the detector rejected. Cluster exactly what
    # the detector would fail on, and it cannot fail by construction.
    HAMMING, JACCARD = WARN_HAMMING, FAIL_JACCARD

    items = [(pid, simhash64(text)) for pid, text in sorted(texts.items())]
    parent: dict[str, str] = {pid: pid for pid, _ in items}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    shingles: dict[str, set[str]] = {}
    hashes = dict(items)
    for a, b in candidate_pairs(items, items):
        if a == b or find(a) == find(b):
            continue
        if hamming(hashes[a], hashes[b]) > HAMMING:
            continue
        for pid in (a, b):
            if pid not in shingles:
                shingles[pid] = char_shingles(texts[pid])
        if jaccard(shingles[a], shingles[b]) >= JACCARD:
            parent[find(a)] = find(b)

    # Lowest id per cluster, so the choice is deterministic.
    keep: dict[str, str] = {}
    for pid in sorted(parent, key=lambda x: (len(x), x)):
        root = find(pid)
        keep.setdefault(root, pid)
    return set(keep.values())


def multiclaim_rows() -> dict[str, list[Row]]:
    return load_multiclaim()


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
    "multiclaim": multiclaim_rows,
}

# What each loader needs on disk. Used to skip a dataset whose source is not
# present rather than crash on it.
#
# This is not hypothetical tidiness: MultiClaim is access-restricted and cannot
# ever exist in CI, so the reproducibility job must be able to verify the
# datasets it CAN fetch and report the rest as unverifiable -- not fail, and not
# quietly pass either.
LOADER_SOURCES: dict[str, tuple[Path, ...]] = {
    "averitec": (RAW / "averitec" / "train.json", RAW / "averitec" / "dev.json"),
    "x_claim": (RAW / "x_claim" / "train-en.csv",),
    "multiclaim": (RAW / "multiclaim" / "posts.csv",
                   RAW / "multiclaim" / "fact_checks.csv",
                   RAW / "multiclaim" / "fact_check_post_mapping.csv"),
}


def sources_available(dataset: str) -> bool:
    return all(p.is_file() for p in LOADER_SOURCES.get(dataset, ()))


def missing_sources(dataset: str) -> list[str]:
    return [p.as_posix() for p in LOADER_SOURCES.get(dataset, ()) if not p.is_file()]


def code_mixed_share(rows: list[Row], threshold: float = 0.9) -> float:
    """Share of rows whose dominant script covers less than `threshold`.

    Reported in docs/data-profile.md because code-mixing is the normal case
    for forwards, and a single `script` label hides it.
    """
    if not rows:
        return 0.0
    mixed = sum(1 for r in rows if script_purity(r.text) < threshold)
    return mixed / len(rows)
