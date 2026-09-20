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
import random
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, write_json, write_jsonl  # noqa: E402
from common.seeds import SEED  # noqa: E402
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


def _is_tracked_by_git(path: Path) -> bool:
    """Has git ever seen this file? Untracked means not yet frozen."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return True  # cannot tell -> assume frozen, the safe direction
    return out.returncode == 0


def freeze_split(
    path: str | Path,
    rows: Sequence[dict[str, Any]],
    *,
    allow_rewrite: bool = False,
    reason: str | None = None,
) -> int:
    """Write a split file, refusing to clobber one that is already frozen.

    "Frozen" means COMMITTED. A split file that exists on disk but that git has
    never seen is still being built -- nothing references it, no results were
    computed against it, and there is nothing to invalidate. Requiring the full
    rewrite ceremony for those would only teach the habit of reaching for the
    override, which is the thing that makes it useless when it matters.
    """
    target = Path(path)
    for i, rec in enumerate(rows, start=1):
        validate_split_record(rec, where=f"{target} (row {i})")

    if target.exists() and not _is_tracked_by_git(target):
        print(f"    (overwriting {target.name}: never committed, so not yet frozen)")
        return write_jsonl(target, rows)

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


def _stratified_holdout(
    rows: list, key, fraction: float, seed: int,
) -> tuple[list, list]:
    """Split rows into (kept, held out), preserving the class balance.

    Used to carve a local test set out of AVeriTeC's public train, because
    AVeriTeC's real test split is withheld for the FEVER shared task. Without
    this there would be no held-out set at all and dev would be doing double
    duty as both the model-selection set and the final reported number --
    exactly the leak the harness exists to prevent.
    """
    buckets: dict[object, list] = {}
    for row in rows:
        buckets.setdefault(key(row), []).append(row)

    rng = random.Random(seed)
    kept: list = []
    held: list = []
    for label in sorted(buckets, key=str):
        bucket = buckets[label][:]
        rng.shuffle(bucket)
        n_held = max(1, round(len(bucket) * fraction)) if len(bucket) > 1 else 0
        held.extend(bucket[:n_held])
        kept.extend(bucket[n_held:])
    return kept, held


def _renumber(rows: list, split: str) -> list:
    """Reassign uid/split after a re-split or a dedup pass.

    Indices run per (language, split) so a uid stays readable. `source_id` is
    the stable anchor back to the upstream record and is never rewritten.
    """
    counters: dict[str, int] = {}
    out = []
    for row in rows:
        rec = dict(row.record)
        rec["split"] = split
        lang = rec["lang"]
        i = counters.get(lang, 0)
        counters[lang] = i + 1
        rec["uid"] = f"{rec['dataset']}:{lang}:{split}:{i:05d}"
        out.append(row._replace(record=rec))
    return out


AVERITEC_TEST_FRACTION = 0.10

# Near-duplicate removal thresholds. A row is dropped from train only when
# BOTH agree, so a SimHash false positive cannot silently shrink the training
# set: the text is on hand in data/interim, so the exact Jaccard is cheap.
DEDUP_HAMMING = 8
DEDUP_JACCARD = 0.80


def deduplicate(rows_by_split: dict[str, list]) -> tuple[dict[str, list], dict[str, Any]]:
    """Resolve leakage by the rule: TRAIN YIELDS TO EVAL.

    Both AVeriTeC and X-CLAIM ship with claims that appear in more than one
    official split -- this is the DS@GT CheckThat! 2025 finding, reproduced.
    There are only two ways to resolve it, and only one of them is honest:

      * Drop the row from dev/test. Shrinks the evaluation set and silently
        changes the benchmark, so our numbers stop being comparable with
        published ones. Rejected.
      * Drop the row from train. Costs a handful of training examples and
        nothing else. Taken.

    So dev and test are never modified here, not even to remove duplicates
    WITHIN themselves -- that would change the benchmark too. Those are
    counted and reported in docs/data-profile.md instead.

    Within-train duplicates are dropped, since they only over-weight examples.
    """
    from data.normalize import char_shingles
    from data.simhash import candidate_pairs, hamming, jaccard

    report: dict[str, Any] = {
        "policy": "train yields to eval; dev and test are never modified",
        "dropped_from_train": {"within_train_duplicate": 0,
                               "exact_match_in_eval": 0,
                               "near_duplicate_in_eval": 0},
        "left_in_place": {},
    }

    eval_rows = [r for name, rows in rows_by_split.items() if name != "train" for r in rows]
    eval_hashes = {r.record["text_sha1"] for r in eval_rows}
    eval_items = [(r.record["uid"], int(r.record["simhash64"], 16)) for r in eval_rows]
    eval_text = {r.record["uid"]: r.text for r in eval_rows}

    train = rows_by_split.get("train", [])
    train_items = [(r.record["uid"], int(r.record["simhash64"], 16)) for r in train]
    train_text = {r.record["uid"]: r.text for r in train}

    # Which train uids are near-duplicates of an eval row?
    near_uids: set[str] = set()
    for eval_uid, train_uid in candidate_pairs(eval_items, train_items):
        a, b = dict(eval_items)[eval_uid], dict(train_items)[train_uid]
        if hamming(a, b) > DEDUP_HAMMING:
            continue
        if jaccard(char_shingles(eval_text[eval_uid]),
                   char_shingles(train_text[train_uid])) >= DEDUP_JACCARD:
            near_uids.add(train_uid)

    kept: list = []
    seen: set[str] = set()
    for row in train:
        sha = row.record["text_sha1"]
        uid = row.record["uid"]
        if sha in seen:
            report["dropped_from_train"]["within_train_duplicate"] += 1
            continue
        if sha in eval_hashes:
            report["dropped_from_train"]["exact_match_in_eval"] += 1
            continue
        if uid in near_uids:
            report["dropped_from_train"]["near_duplicate_in_eval"] += 1
            continue
        seen.add(sha)
        kept.append(row)

    out = dict(rows_by_split)
    out["train"] = kept

    # Count, but do not touch, what remains in the evaluation splits.
    for name, rows in rows_by_split.items():
        if name == "train":
            continue
        hashes = [r.record["text_sha1"] for r in rows]
        report["left_in_place"][f"{name}_internal_duplicates"] = len(hashes) - len(set(hashes))
    dev_h = {r.record["text_sha1"] for r in rows_by_split.get("dev", [])}
    test_h = {r.record["text_sha1"] for r in rows_by_split.get("test", [])}
    report["left_in_place"]["dev_test_overlap"] = len(dev_h & test_h)

    return out, report


def cmd_build(args) -> int:
    """Materialise the raw downloads into frozen splits."""
    from data.loaders import LOADERS, code_mixed_share

    datasets = [args.dataset] if args.dataset else sorted(LOADERS)
    downloads = load_json(Path("data/raw/DOWNLOADS.json")) if \
        Path("data/raw/DOWNLOADS.json").is_file() else {}

    for name in datasets:
        print(f"\n{name}")
        rows_by_split = LOADERS[name]()

        notes: list[str] = []
        if name == "averitec":
            train, test = _stratified_holdout(
                rows_by_split["train"],
                key=lambda r: r.record["label"],
                fraction=AVERITEC_TEST_FRACTION,
                seed=SEED,
            )
            rows_by_split["train"] = _renumber(train, "train")
            rows_by_split["test"] = _renumber(test, "test")
            notes.append(
                f"AVeriTeC's real test split is withheld for the FEVER shared task, so "
                f"{AVERITEC_TEST_FRACTION:.0%} of the public train split was held out as a "
                f"local test set, stratified by label with seed {SEED}. The official dev "
                "split is used unchanged, so dev numbers stay comparable to published work; "
                "train is correspondingly smaller than the official train."
            )

        rows_by_split, dedup = deduplicate(rows_by_split)
        rows_by_split["train"] = _renumber(rows_by_split["train"], "train")
        dropped = dedup["dropped_from_train"]
        if sum(dropped.values()):
            print(f"  dedup: dropped {sum(dropped.values())} train rows "
                  + ", ".join(f"{k}={v}" for k, v in dropped.items() if v))
        if any(dedup["left_in_place"].values()):
            print("  left in place (never modify an eval split): "
                  + ", ".join(f"{k}={v}" for k, v in dedup["left_in_place"].items() if v))

        manifest_counts: dict[str, dict[str, int]] = {}
        for split, rows in sorted(rows_by_split.items()):
            records = [r.record for r in rows]
            target = SPLITS_ROOT / name / f"{split}.jsonl"
            n = freeze_split(
                target, records,
                allow_rewrite=args.allow_rewrite,
                reason=args.reason,
            )
            # Text stays local: data/interim/ is gitignored.
            write_jsonl(
                Path("data/interim") / name / f"{split}.jsonl",
                [{"uid": r.record["uid"], "text": r.text} for r in rows],
            )
            counts = per_split_counts({split: records})[split]
            manifest_counts[split] = counts
            mixed = code_mixed_share(rows)
            print(f"  {split:<6} n={n:<6} "
                  + " ".join(f"{k}={v}" for k, v in counts.items() if "/" in k)
                  + f"  code-mixed={mixed:.1%}")

        write_json(SPLITS_ROOT / name / "MANIFEST.json", {
            "dataset": name,
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "seed": SEED,
            "source": downloads.get(name, {}),
            "notes": notes,
            "deduplication": dedup,
            "counts": manifest_counts,
        })

    return cmd_lock(argparse.Namespace(force=True))


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

    build = sub.add_parser("build", help="materialise data/raw into frozen splits")
    build.add_argument("--dataset", help="build only this dataset")
    build.add_argument("--i-know-this-regenerates-frozen-splits", dest="allow_rewrite",
                       action="store_true")
    build.add_argument("--reason", help="why an existing frozen split is being rewritten")

    sub.add_parser("status", help="show datasets and per-language counts")
    sub.add_parser("verify", help="check splits against SPLITS.lock")
    lock = sub.add_parser("lock", help="(re)write SPLITS.lock")
    lock.add_argument("--force", action="store_true",
                      help="re-lock even though the splits disagree with the current lock")

    args = parser.parse_args(argv)
    handlers = {"build": cmd_build, "status": cmd_status,
                "verify": cmd_verify, "lock": cmd_lock}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
