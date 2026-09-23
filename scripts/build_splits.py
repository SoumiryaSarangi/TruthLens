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
    python scripts/build_splits.py verify-reproducible   # rebuild and compare
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

from common.hashing import sha256_file  # noqa: E402
from common.io_jsonl import load_json, load_jsonl, write_json, write_jsonl  # noqa: E402
from common.seeds import SEED  # noqa: E402
from data.leakage import per_split_counts  # noqa: E402
from data.splits import (  # noqa: E402
    LOCK_PATH,
    build_lock,
    discover_splits,
    load_split,
    read_lock,
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


def _would_be_identical(target: Path, rows: Sequence[dict[str, Any]]) -> bool:
    """Would writing `rows` leave the file byte-for-byte as it is?

    Serialised exactly as `common.io_jsonl.write_jsonl` does -- sorted keys,
    compact separators, LF -- because "identical" has to mean identical to what
    would actually be written, not to a near-enough rendering of it.
    """
    import json

    expected = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    try:
        with target.open("r", encoding="utf-8", newline="") as fh:
            return fh.read() == expected
    except OSError:  # pragma: no cover - unreadable file is not "identical"
        return False


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
        # A rewrite that changes nothing is not a rewrite. Rebuilding a dataset
        # re-freezes all of its splits, so dev and test get written even when the
        # dedup only touched train -- and logging those as changes makes the
        # changelog lie, because its header says an entry means prior results are
        # no longer comparable.
        if _would_be_identical(target, rows):
            print(f"    ({target.name}: byte-identical, not logged as a change)")
            return write_jsonl(target, rows)

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


def load_external_evals(exclude: str, splits_root: Path, interim_root: Path) -> dict[str, Any]:
    """Every dev/test row from every OTHER dataset already on disk.

    This exists because "train yields to eval" was only ever applied WITHIN a
    dataset, and that was not enough the moment two datasets turned out to share
    a post pool. CheckThat! 2025 Task 2 and X-CLAIM overlap heavily -- 400 of
    CheckThat's dev posts are in X-CLAIM's train split, which is 32% of that dev
    set. Training on one and evaluating on the other would have measured
    memorisation.

    Nothing here modifies an eval split. It only tells the caller which train
    rows have to go.
    """
    hashes: set[str] = set()
    items: list[tuple[str, int]] = []
    texts: dict[str, str] = {}
    if not splits_root.is_dir():
        return {"hashes": hashes, "items": items, "texts": texts}
    for dataset_dir in sorted(splits_root.iterdir()):
        if not dataset_dir.is_dir() or dataset_dir.name == exclude:
            continue
        text_by_uid: dict[str, str] = {}
        for split in ("dev", "test"):
            interim = interim_root / dataset_dir.name / f"{split}.jsonl"
            if interim.is_file():
                text_by_uid.update({r["uid"]: r["text"] for r in load_jsonl(interim)})
        for split in ("dev", "test"):
            path = dataset_dir / f"{split}.jsonl"
            if not path.is_file():
                continue
            for record in load_jsonl(path):
                hashes.add(record["text_sha1"])
                items.append((record["uid"], int(record["simhash64"], 16)))
                if record["uid"] in text_by_uid:
                    texts[record["uid"]] = text_by_uid[record["uid"]]
    return {"hashes": hashes, "items": items, "texts": texts}


def deduplicate(rows_by_split: dict[str, list],
                external_eval: dict[str, Any] | None = None,
                ) -> tuple[dict[str, list], dict[str, Any]]:
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

    # Other datasets' eval splits count too -- but by EXACT hash only.
    #
    # Near-duplicate detection needs the text on both sides to confirm a SimHash
    # candidate with Jaccard, and a committed split carries ids and hashes, not
    # text. MultiClaim's text can never exist on a CI runner, so using it here
    # would make x_claim/train's CONTENT depend on data CI cannot read: the same
    # build produced 4,398 rows locally and 4,446 on the runner, and the
    # reproducibility job caught it.
    #
    # A public split has to be rebuildable from public data. So the cross-dataset
    # rule is exact-match, which is reproducible everywhere because `text_sha1`
    # is committed. That catches 884 of the 932 leaking rows; the remaining ~48
    # near-duplicates are REPORTED below rather than silently dropped, so the gap
    # is visible instead of being a comfortable assumption.
    #
    # Within a dataset, near-duplicate detection is unchanged -- if the dataset is
    # buildable at all, its own text is present.
    external = external_eval or {"hashes": set(), "items": [], "texts": {}}
    external_hashes = set(external["hashes"])
    external_items = list(external["items"])
    external_text = dict(external["texts"])
    report["dropped_from_train"]["in_another_dataset_eval_split"] = 0

    train = rows_by_split.get("train", [])
    train_items = [(r.record["uid"], int(r.record["simhash64"], 16)) for r in train]
    train_text = {r.record["uid"]: r.text for r in train}

    # Which train uids are near-duplicates of an eval row?
    near_uids: set[str] = set()
    unverifiable = 0
    for eval_uid, train_uid in candidate_pairs(eval_items, train_items):
        a, b = dict(eval_items)[eval_uid], dict(train_items)[train_uid]
        if hamming(a, b) > DEDUP_HAMMING:
            continue
        # A committed split always has its ids; its TEXT only exists where the
        # source data does. MultiClaim is access-restricted, so on a CI runner
        # its split files are present and data/interim/multiclaim/ is not --
        # which means a SimHash candidate against it cannot be confirmed by
        # Jaccard. Counted and reported rather than treated as a non-match: the
        # exact-hash check above still catches identical text, so what is lost
        # here is only near-duplicate detection against data we cannot read.
        eval_side = eval_text.get(eval_uid)
        train_side = train_text.get(train_uid)
        if eval_side is None or train_side is None:
            unverifiable += 1
            continue
        if jaccard(char_shingles(eval_side), char_shingles(train_side)) >= DEDUP_JACCARD:
            near_uids.add(train_uid)
    if unverifiable:
        report["near_duplicate_candidates_unverifiable_no_text"] = unverifiable

    # Cross-dataset NEAR duplicates: reported, never acted on. Acting on them
    # would make this split unreproducible wherever the other dataset's text is
    # absent. Counted only when the text happens to be readable, so this number
    # is environment-dependent -- which is exactly why it must not change what
    # gets written.
    cross_near = 0
    if external_items and external_text:
        train_by_uid = dict(train_items)
        ext_by_uid = dict(external_items)
        for eval_uid, train_uid in candidate_pairs(external_items, train_items):
            if hamming(ext_by_uid[eval_uid], train_by_uid[train_uid]) > DEDUP_HAMMING:
                continue
            a, b = external_text.get(eval_uid), train_text.get(train_uid)
            if a is None or b is None:
                continue
            if jaccard(char_shingles(a), char_shingles(b)) >= DEDUP_JACCARD:
                cross_near += 1
    report["cross_dataset_near_duplicates_reported_not_dropped"] = cross_near

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
        if sha in external_hashes:
            report["dropped_from_train"]["in_another_dataset_eval_split"] += 1
            continue
        if uid in near_uids:
            report["dropped_from_train"]["near_duplicate_in_eval"] += 1
            continue
        seen.add(sha)
        kept.append(row)

    out = dict(rows_by_split)
    # Only if the dataset HAS a train split. Writing the key unconditionally
    # gave the eval-only handtyped set an empty train.jsonl, which the lock then
    # recorded -- and "a train split exists and is empty" is a different claim
    # from "this dataset has no train split".
    if "train" in rows_by_split:
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
    from data.loaders import LOADERS, code_mixed_share, missing_sources, sources_available

    out_root = Path(getattr(args, "out_dir", None) or SPLITS_ROOT)
    interim_root = Path(getattr(args, "interim_dir", None) or "data/interim")
    datasets = [args.dataset] if args.dataset else sorted(LOADERS)
    downloads = load_json(Path("data/raw/DOWNLOADS.json")) if \
        Path("data/raw/DOWNLOADS.json").is_file() else {}

    skipped: list[str] = []
    for name in datasets:
        print(f"\n{name}")
        # A dataset whose source is absent is skipped, not fatal. MultiClaim is
        # access-restricted and can never be present in CI, so the build has to
        # do what it can and say what it could not.
        if not sources_available(name):
            print(f"  SKIPPED: source data not present ({', '.join(missing_sources(name))})")
            skipped.append(name)
            continue
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

        # Always the REAL committed splits, never `out_root`. A reproducibility
        # check builds into a temp directory, and reading eval splits from there
        # would find none -- so the rebuild would skip cross-dataset dedup and
        # fail to reproduce the very files it is checking. Eval splits are
        # committed by definition, so this is always the right source.
        external = load_external_evals(name, SPLITS_ROOT, Path("data/interim"))
        if external["hashes"]:
            print(f"  checking against {len(external['hashes'])} eval rows from "
                  f"other datasets")
        rows_by_split, dedup = deduplicate(rows_by_split, external_eval=external)
        if "train" in rows_by_split:
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
            target = out_root / name / f"{split}.jsonl"
            n = freeze_split(
                target, records,
                allow_rewrite=args.allow_rewrite,
                reason=args.reason,
            )
            # Text stays local: data/interim/ is gitignored.
            write_jsonl(
                interim_root / name / f"{split}.jsonl",
                [{"uid": r.record["uid"], "text": r.text} for r in rows],
            )
            counts = per_split_counts({split: records})[split]
            manifest_counts[split] = counts
            mixed = code_mixed_share(rows)
            print(f"  {split:<6} n={n:<6} "
                  + " ".join(f"{k}={v}" for k, v in counts.items() if "/" in k)
                  + f"  code-mixed={mixed:.1%}")

        write_json(out_root / name / "MANIFEST.json", {
            "dataset": name,
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "seed": SEED,
            "source": downloads.get(name, {}),
            "notes": notes,
            "deduplication": dedup,
            "counts": manifest_counts,
        })

    if skipped:
        print(f"\n  skipped (no source data): {', '.join(skipped)}")
    if out_root != SPLITS_ROOT:
        return 0
    if skipped and not args.dataset:
        print("  NOT re-locking: a skipped dataset would be dropped from SPLITS.lock")
        return 0
    return cmd_lock(argparse.Namespace(force=True))


def cmd_verify_reproducible(args) -> int:
    """Rebuild from data/raw into a temp dir and compare against SPLITS.lock.

    Proves the committed splits can be regenerated from the recorded sources.
    It must NOT write to data/splits/: those files are committed, so
    freeze_split would rightly refuse, and a check that fights the guardrail
    it depends on is not a check.

    Only the split .jsonl files are compared. MANIFEST.json carries a
    created_utc timestamp and so differs on every build by design; SPLITS.lock
    is the thing that actually pins content.
    """
    import tempfile

    if not LOCK_PATH.is_file():
        print(f"No {LOCK_PATH}; nothing to verify.")
        return 0
    locked = read_lock(LOCK_PATH)

    with tempfile.TemporaryDirectory() as tmp:
        out_root = Path(tmp) / "splits"
        # Splits go to a temp dir so the committed ones are never touched, but
        # the materialised text lands in data/interim, where the leakage test
        # looks for it. That makes the near-duplicate check confirmable on a
        # clean clone -- including in CI.
        rc = cmd_build(argparse.Namespace(
            dataset=args.dataset, allow_rewrite=False, reason=None,
            out_dir=str(out_root), interim_dir="data/interim",
        ))
        if rc != 0:
            return rc

        from data.loaders import sources_available

        problems: list[str] = []
        unverifiable: list[str] = []
        for key, entry in sorted(locked.items()):
            dataset = key.split("/")[0]
            if args.dataset and dataset != args.dataset:
                continue
            if not sources_available(dataset):
                unverifiable.append(key)
                continue
            rebuilt = out_root / key
            if not rebuilt.is_file():
                problems.append(f"{key}: in SPLITS.lock but the rebuild did not produce it")
                continue
            digest = sha256_file(rebuilt)
            if digest != entry.sha256:
                problems.append(
                    f"{key}: rebuild does NOT match the committed split\n"
                    f"    committed: {entry.sha256}\n"
                    f"    rebuilt  : {digest}"
                )

    print()
    if problems:
        print("SPLITS ARE NOT REPRODUCIBLE FROM SOURCE:\n")
        for prob in problems:
            print(f"  - {prob}")
        print("\nEither the upstream data changed -- compare the sha256 values in "
              "data/raw/DOWNLOADS.json -- or the build became non-deterministic.")
        return 1
    if unverifiable:
        print(f"  {len(unverifiable)} split file(s) could NOT be checked -- their source "
              "data is not present here (restricted datasets are never in CI):")
        for key in unverifiable:
            print(f"    - {key}")
    checked = len(locked) - len(unverifiable)
    print(f"OK: all {checked} checkable split file(s) reproduce byte-for-byte from data/raw/")
    return 0


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
    build.add_argument("--interim-dir", dest="interim_dir",
                       help="where to write materialised text (default data/interim)")
    build.add_argument("--out-dir", dest="out_dir",
                       help="write splits here instead of data/splits (used by "
                            "verify-reproducible; skips locking)")

    repro = sub.add_parser("verify-reproducible",
                           help="rebuild from data/raw in a temp dir and compare to SPLITS.lock")
    repro.add_argument("--dataset", help="check only this dataset")

    sub.add_parser("status", help="show datasets and per-language counts")
    sub.add_parser("verify", help="check splits against SPLITS.lock")
    lock = sub.add_parser("lock", help="(re)write SPLITS.lock")
    lock.add_argument("--force", action="store_true",
                      help="re-lock even though the splits disagree with the current lock")

    args = parser.parse_args(argv)
    handlers = {"build": cmd_build, "status": cmd_status,
                "verify": cmd_verify, "lock": cmd_lock,
                "verify-reproducible": cmd_verify_reproducible}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
