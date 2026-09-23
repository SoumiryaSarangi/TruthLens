"""Generate docs/data-profile.md from the frozen splits.

    make profile

Never write that file by hand. It is the record of what is actually in
data/splits/, and a hand-edited number in it is worse than no number: it looks
authoritative and cannot be reproduced.

Reports, per dataset: counts by split x language x script, label distribution
with the majority-class rate (the dumb baseline any classifier must beat),
text length, code-mixing, and the leakage position after deduplication.
"""

from __future__ import annotations

import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, load_jsonl  # noqa: E402
from data.leakage import (  # noqa: E402
    failures,
    filter_accepted,
    find_leakage,
    load_accepted,
)
from data.script_id import script_purity  # noqa: E402
from data.splits import discover_splits, load_split  # noqa: E402

SPLITS_ROOT = Path("data/splits")
INTERIM = Path("data/interim")
OUT = Path("docs/data-profile.md")

SPLIT_ORDER = ("train", "dev", "test")
LANGS = ("en", "hi", "pa")
SCRIPTS = ("deva", "guru", "latn")
NATIVE = {"hi": "deva", "pa": "guru", "en": "latn"}


def _texts(dataset: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for split in SPLIT_ORDER:
        path = INTERIM / dataset / f"{split}.jsonl"
        if path.is_file():
            out.update({r["uid"]: r["text"] for r in load_jsonl(path)})
    return out


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def profile_dataset(name: str, paths: dict[str, Path]) -> str:
    splits = {s: load_split(p) for s, p in paths.items()}
    ordered = [s for s in SPLIT_ORDER if s in splits]
    texts = _texts(name)
    manifest_path = SPLITS_ROOT / name / "MANIFEST.json"
    manifest = load_json(manifest_path) if manifest_path.is_file() else {}

    out: list[str] = [f"## {name}", ""]

    source = manifest.get("source", {})
    if source:
        out += [f"Source: {source.get('repo', '?')} — {source.get('licence', 'licence: ?')}", ""]
    for note in manifest.get("notes", []):
        out += [f"> {note}", ""]

    # -- counts by split x language x script ---------------------------------
    out += ["### Counts by split, language and script", ""]
    header = ["split", "n"] + [f"{lang}/{sc}" for lang in LANGS for sc in SCRIPTS]
    rows = []
    for split in ordered:
        cells = Counter((r["lang"], r["script"]) for r in splits[split])
        row = [split, str(len(splits[split]))]
        row += [str(cells.get((lang, sc), 0) or "·") for lang in LANGS for sc in SCRIPTS]
        rows.append(row)
    # Drop all-empty columns so the table stays readable.
    keep = [0, 1] + [i for i in range(2, len(header))
                     if any(r[i] != "·" for r in rows)]
    out += [_table([header[i] for i in keep], [[r[i] for i in keep] for r in rows]), ""]

    # -- romanized share -----------------------------------------------------
    roman_rows = []
    for split in ordered:
        for lang in LANGS:
            rows_l = [r for r in splits[split] if r["lang"] == lang]
            if not rows_l:
                continue
            native = sum(1 for r in rows_l if r["script"] == NATIVE[lang])
            other = len(rows_l) - native
            roman_rows.append([
                split, lang, str(len(rows_l)), str(native), str(other),
                f"{other / len(rows_l):.1%}",
            ])
    if roman_rows:
        out += ["### Non-native-script share", "",
                "The romanized-vs-native axis. `other` is every row not in the language's "
                "own script, which for hi/pa is mostly Latin (romanized) plus some "
                "cross-script contamination in the source files.", "",
                _table(["split", "lang", "n", "native", "other", "other %"], roman_rows), ""]

    # -- labels --------------------------------------------------------------
    labelled = {s: [r for r in splits[s] if r.get("label")] for s in ordered}
    if any(labelled.values()):
        out += ["### Label distribution", "",
                "`majority %` is the dumb baseline: a classifier that always predicts the "
                "most frequent class. Any model must beat it to be a result.", ""]
        all_labels = sorted({r["label"] for rows_ in labelled.values() for r in rows_})
        rows = []
        for split in ordered:
            counts = Counter(r["label"] for r in labelled[split])
            total = sum(counts.values())
            if not total:
                continue
            row = [split, str(total)]
            row += [f"{counts.get(lab, 0)} ({counts.get(lab, 0) / total:.0%})"
                    for lab in all_labels]
            row.append(f"{max(counts.values()) / total:.1%}")
            rows.append(row)
        out += [_table(["split", "n", *all_labels, "majority %"], rows), ""]

    # -- text length and code-mixing -----------------------------------------
    len_rows = []
    for split in ordered:
        lengths = [r["n_chars"] for r in splits[split]]
        mixed = [texts[r["uid"]] for r in splits[split] if r["uid"] in texts]
        mixed_share = (sum(1 for t in mixed if script_purity(t) < 0.9) / len(mixed)
                       if mixed else None)
        len_rows.append([
            split, str(len(lengths)),
            str(min(lengths)), str(round(statistics.median(lengths))),
            str(round(statistics.mean(lengths))), str(max(lengths)),
            f"{mixed_share:.1%}" if mixed_share is not None else "—",
        ])
    out += ["### Text length (characters) and code-mixing", "",
            _table(["split", "n", "min", "median", "mean", "max", "code-mixed"], len_rows),
            "",
            "_code-mixed = share of rows whose dominant script covers under 90% of "
            "their script-bearing characters. Computed from data/interim/, so it shows "
            "`—` on a clean clone until `make data` has run._", ""]

    # -- deduplication --------------------------------------------------------
    dedup = manifest.get("deduplication")
    if dedup:
        dropped = dedup.get("dropped_from_train", {})
        left = dedup.get("left_in_place", {})
        out += ["### Deduplication applied when building these splits", "",
                f"Policy: **{dedup.get('policy', '?')}**", "",
                _table(["action", "rows"],
                       [[f"dropped from train — {k.replace('_', ' ')}", str(v)]
                        for k, v in dropped.items()]
                       + [[f"left in place — {k.replace('_', ' ')}", str(v)]
                          for k, v in left.items()]),
                ""]

    # -- leakage position -----------------------------------------------------
    found = find_leakage(name, splits, texts=texts or None)
    unaccepted, accepted = filter_accepted(found, load_accepted())
    fails = failures(unaccepted)
    out += ["### Leakage after deduplication", "",
            f"- unresolved failures: **{len(fails)}**",
            f"- accepted as irreducible upstream: **{len(accepted)}** "
            "(see `data/splits/KNOWN_LEAKAGE.json`)",
            f"- warnings (unconfirmed near-duplicates): {len(unaccepted) - len(fails)}",
            ""]
    for entry in accepted:
        out += [f"  - `{entry.uid_a}` ↔ `{entry.uid_b}` "
                f"({entry.split_a}/{entry.split_b}, jaccard "
                f"{entry.jaccard:.3f})" if entry.jaccard else
                f"  - `{entry.uid_a}` ↔ `{entry.uid_b}`"]
    if accepted:
        out += [""]
    return "\n".join(out)


def main() -> int:
    found = discover_splits(SPLITS_ROOT)
    if not found:
        print(f"No datasets under {SPLITS_ROOT}; nothing to profile.")
        return 0

    parts = [
        "# Data profile",
        "",
        "_Generated by `make profile` (scripts/profile_data.py). Do not edit by hand._",
        "",
        "Counts come from the frozen splits in `data/splits/`, not from the raw "
        "downloads, so this describes exactly what the models will see.",
        "",
    ]
    for name, paths in found.items():
        parts.append(profile_dataset(name, paths))

    # Checked on disk, not asserted. A hardcoded status is how a document ends
    # up telling a future reader to acquire something they already have.
    dakshina = Path("data/raw/dakshina/extracted")
    dakshina_langs = sorted(p.name for p in dakshina.glob("*") if p.is_dir())
    parts += [
        "## Supporting corpora (not split, so not profiled above)",
        "",
        "| Dataset | Status |",
        "| --- | --- |",
        (f"| Dakshina | Downloaded and extracted for {', '.join(dakshina_langs)}. "
         "Its TEST half trains the romanized language-ID classifier; its DEV half "
         "is reserved for transliteration evaluation, so no row is both trained on "
         "and evaluated on. |") if dakshina_langs else
        "| Dakshina | Not downloaded. Needed to evaluate transliteration in Phase 2. |",
        "",
        "## Not yet acquired",
        "",
        "| Dataset | Status |",
        "| --- | --- |",
        "| CheckThat! 2025 Task 2 | Not started. Needed for Phase 3 claim normalization. |",
        "",
    ]
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
