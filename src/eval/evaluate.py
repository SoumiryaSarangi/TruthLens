"""The eval harness. The only sanctioned way to turn predictions into a number.

    make eval CONFIG=configs/<name>.yaml

Takes a predictions JSONL and a config YAML, emits results/{config_hash}.json.

It refuses to produce a number it cannot stand behind. Five guardrails, each
one enforcing a rule that already exists in CLAUDE.md:

  1. `baseline:` is mandatory. No baseline, no results file.
     ("A model without a baseline comparison is not a result.")
  2. Evaluating a `test` split aborts unless TRUTHLENS_ALLOW_TEST=1.
     (Stops the test set being touched during model selection.)
  3. A split file whose bytes disagree with SPLITS.lock aborts.
     ("NEVER regenerate files in data/splits/.")
  4. A metric above `sanity_ceiling` writes a loud warning into the JSON.
     ("Target is ~50%; do not tune toward suspiciously high numbers.")
  5. Duplicate, unknown or missing uids abort unless allow_partial is set.
     (Silent partial evaluation is how coverage gaps become fake gains.)

Exit codes: 0 success, 2 the run was refused, 1 an unexpected error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from common.hashing import canonical_json, sha256_bytes, sha256_file
from common.io_jsonl import JsonlError, load_json, load_jsonl, write_json
from common.provenance import env_info, git_info
from common.seeds import SEED, set_all_seeds
from data.labels import get_label_set, validate_labels
from data.splits import SplitError, load_split, read_lock
from eval import baselines as baselines_mod
from eval import metrics as M
from eval.breakdown import MIN_CELL_N, compute_with_breakdown, script_gap

SCHEMA_PATH = Path("configs/_schema/eval.schema.json")
DEFAULT_OUT_DIR = Path("results")
CONFIG_HASH_LEN = 12

# A headline metric above this is a warning, not an error: it might be real on
# an easy slice. It must never pass silently.
DEFAULT_SANITY_CEILING = 0.85
_HASH_RE = re.compile(rf"^[0-9a-f]{{{CONFIG_HASH_LEN}}}$")


class EvalRefused(Exception):
    """The harness declined to produce a number. Exit code 2."""


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "seed": SEED,
    "min_cell_n": MIN_CELL_N,
    "allow_partial": False,
    "breakdown": ["lang", "script"],
    "metrics": {},
    "sanity_ceiling": DEFAULT_SANITY_CEILING,
}


def load_config(path: str | Path, schema_path: str | Path = SCHEMA_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise EvalRefused(f"config not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise EvalRefused(f"{p}: config must be a YAML mapping")

    schema = load_json(schema_path)
    try:
        jsonschema.validate(raw, schema)
    except jsonschema.ValidationError as exc:
        where = "/".join(str(x) for x in exc.absolute_path) or "(root)"
        raise EvalRefused(f"{p}: invalid config at {where}: {exc.message}") from None

    return {**DEFAULTS, **raw}


# -----------------------------------------------------------------------------
# Guardrails
# -----------------------------------------------------------------------------


def guard_baseline(cfg: dict[str, Any]) -> None:
    """Guardrail 1."""
    baseline = str(cfg.get("baseline", "")).strip()
    if not baseline:
        raise EvalRefused(
            "config has no `baseline:`. CLAUDE.md: 'Compare every model against the "
            "dumb baseline in the same table. A model without a baseline comparison "
            f"is not a result.' Registered baselines: {sorted(baselines_mod.REGISTRY)}."
        )
    if not baselines_mod.is_registered(baseline) and not _HASH_RE.match(baseline):
        raise EvalRefused(
            f"baseline {baseline!r} is neither a registered baseline "
            f"({sorted(baselines_mod.REGISTRY)}) nor a {CONFIG_HASH_LEN}-char config_hash "
            "of a previous run."
        )


def guard_test_split(split_path: Path, split_rows: list[dict[str, Any]]) -> None:
    """Guardrail 2."""
    is_test = split_path.stem == "test" or any(r.get("split") == "test" for r in split_rows)
    if is_test and os.environ.get("TRUTHLENS_ALLOW_TEST") != "1":
        raise EvalRefused(
            f"{split_path} is a TEST split.\n"
            "The test set is for the final reported number, not for model selection. "
            "Every time it is looked at, it becomes a little less of a test set.\n"
            "If this really is the final run, set TRUTHLENS_ALLOW_TEST=1 and say so in "
            "the config's `notes:`."
        )


def find_lock_for(split_path: Path) -> Path | None:
    """Nearest SPLITS.lock at or above the split file, within 3 levels."""
    current = split_path.resolve().parent
    for _ in range(3):
        candidate = current / "SPLITS.lock"
        if candidate.is_file():
            return candidate
        current = current.parent
    return None


def guard_split_frozen(split_path: Path) -> tuple[str, str | None]:
    """Guardrail 3. Returns (split sha256, splits-lock sha256 or None)."""
    split_sha = sha256_file(split_path)
    lock_path = find_lock_for(split_path)
    if lock_path is None:
        return split_sha, None

    locked = read_lock(lock_path)
    # Lock keys are POSIX paths relative to the lock file's own directory.
    try:
        key = split_path.resolve().relative_to(lock_path.parent.resolve()).as_posix()
    except ValueError:  # pragma: no cover - defensive
        key = split_path.as_posix()

    entry = locked.get(key)
    if entry is None:
        raise EvalRefused(
            f"{split_path} is not listed in {lock_path}. A split that is not locked "
            "cannot be verified, and an unverifiable split invalidates every number "
            "derived from it. Run `make lock` if this split was just built."
        )
    if entry.sha256 != split_sha:
        raise EvalRefused(
            f"{split_path} does not match {lock_path}.\n"
            f"    locked: {entry.sha256}\n"
            f"    ondisk: {split_sha}\n"
            "A frozen split has been modified. CLAUDE.md: 'NEVER regenerate files in "
            "data/splits/. If a split file seems wrong, stop and ask.'"
        )
    return split_sha, sha256_file(lock_path)


def check_coverage(
    gold_uids: list[str], pred_by_uid: dict[str, Any], *, allow_partial: bool,
    universe: set[str] | None = None,
) -> dict[str, Any]:
    """Guardrail 5.

    `gold_uids` is what must be predicted; `universe` is what may be. They are
    the same set for classification and retrieval. They differ for
    transliteration, where the split has 100 rows but only 33 carry a reference:
    predicting all 100 is correct and must not be reported as 67 stray uids,
    while failing to predict one of the 33 still has to be caught.
    """
    gold_set = set(gold_uids)
    allowed = universe if universe is not None else gold_set
    missing = sorted(gold_set - set(pred_by_uid))
    unknown = sorted(set(pred_by_uid) - allowed)

    if unknown:
        raise EvalRefused(
            f"{len(unknown)} prediction uid(s) are not in the split, e.g. {unknown[:5]}. "
            "Predicting on rows outside the evaluation set means the two files describe "
            "different experiments."
        )
    if missing and not allow_partial:
        raise EvalRefused(
            f"{len(missing)} of {len(gold_set)} split rows have no prediction, "
            f"e.g. {missing[:5]}. Set `allow_partial: true` to score the covered subset "
            "(coverage is always recorded in the results JSON)."
        )
    return {
        "n_gold": len(gold_set),
        "n_predicted": len(pred_by_uid),
        "n_missing": len(missing),
        "coverage": (len(gold_set) - len(missing)) / len(gold_set) if gold_set else 0.0,
    }


def collect_sanity_warnings(metrics: dict[str, Any], ceiling: float) -> list[str]:
    """Guardrail 4."""
    warnings: list[str] = []
    for name, value in metrics.get("overall", {}).items():
        if not isinstance(value, (int, float)) or name in {"n", "n_skipped_no_relevant"}:
            continue
        # CER and WER are error rates: high is bad, not suspicious. Warning on
        # them would train the reader to ignore this warning.
        if name in {"cer", "wer"}:
            continue
        if value > ceiling:
            warnings.append(
                f"SUSPICIOUSLY HIGH: overall {name}={value:.4f} exceeds sanity_ceiling "
                f"{ceiling}. docs/build-plan.md puts competitive AVeriTeC accuracy at "
                "~47-50%. Before believing this, check: is the test set leaking into "
                "training, is the baseline scoring just as high, is the gold file the "
                "one you think it is?"
            )
    return warnings


# -----------------------------------------------------------------------------
# Predictions
# -----------------------------------------------------------------------------


def load_predictions(path: str | Path, task: str) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        raise EvalRefused(f"predictions not found: {p}")
    required = {"retrieval": ("uid", "ranked_ids"),
                "classification": ("uid", "pred"),
                "transliteration": ("uid", "transliterated"),
                "span": ("uid", "bio"),
                "normalization": ("uid", "normalized"),
                "faithfulness": ("uid", "explanation")}[task]

    by_uid: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(load_jsonl(p), start=1):
        missing = [f for f in required if f not in row]
        if missing:
            raise EvalRefused(f"{p}:{i}: prediction missing field(s) {missing} for task {task}")
        uid = row["uid"]
        if uid in by_uid:
            raise EvalRefused(
                f"{p}:{i}: duplicate uid {uid!r}. Which of the two predictions counts is "
                "not something the harness should be guessing."
            )
        by_uid[uid] = row
    return by_uid


def load_gold_retrieval(path: str | Path) -> dict[str, list[str]]:
    p = Path(path)
    if not p.is_file():
        raise EvalRefused(f"gold file not found: {p}")
    gold: dict[str, list[str]] = {}
    for i, row in enumerate(load_jsonl(p), start=1):
        if "uid" not in row:
            raise EvalRefused(f"{p}:{i}: gold rows need a `uid`")
        # Retrieval gold is a SET of relevant ids; transliteration gold is one
        # reference string. Both are carried as a list so everything downstream
        # -- coverage, breakdown, refusals -- has exactly one shape to handle.
        if "relevant_ids" in row:
            gold[row["uid"]] = list(row["relevant_ids"])
        elif "reference" in row:
            gold[row["uid"]] = [row["reference"]]
        elif "bio" in row:
            # A BIO tag sequence is already a list of strings, which is why span
            # gold needed no new shape here.
            gold[row["uid"]] = list(row["bio"])
        else:
            raise EvalRefused(
                f"{p}:{i}: gold rows need `relevant_ids` (retrieval), "
                f"`reference` (transliteration/normalization) or `bio` (span)"
            )
    return gold


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------


def score_classification(
    split_rows: list[dict[str, Any]],
    pred_by_uid: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    label_set_name = cfg["label_set"]
    labels = get_label_set(label_set_name)
    # Which split column holds the gold. Almost always `label`; `lang` is what
    # makes language identification (FR-3) scoreable, since the answer for a row
    # is the language the row already declares. Restricted to real split fields
    # so a typo cannot silently score against nothing.
    gold_field = cfg.get("gold_field", "label")

    scored = [r for r in split_rows if r["uid"] in pred_by_uid]
    missing_gold = [r["uid"] for r in scored if r.get(gold_field) is None]
    if missing_gold:
        raise EvalRefused(
            f"{len(missing_gold)} split row(s) have no gold `{gold_field}`, e.g. "
            f"{missing_gold[:5]}. A classification split must carry its gold labels."
        )

    y_true = [r[gold_field] for r in scored]
    y_pred = [pred_by_uid[r["uid"]]["pred"] for r in scored]
    try:
        validate_labels(y_true, label_set_name, where=f"{cfg['split']} (gold)")
        validate_labels(y_pred, label_set_name, where=f"{cfg['predictions']} (predicted)")
    except ValueError as exc:
        raise EvalRefused(str(exc)) from None

    def compute(indices) -> dict[str, Any]:
        return M.classification_metrics(
            [y_true[i] for i in indices], [y_pred[i] for i in indices], labels,
        )

    return compute_with_breakdown(
        scored, cfg["breakdown"], compute, min_cell_n=cfg["min_cell_n"],
    )


def score_retrieval(
    split_rows: list[dict[str, Any]],
    pred_by_uid: dict[str, dict[str, Any]],
    gold: dict[str, list[str]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    ks = tuple(cfg.get("metrics", {}).get("retrieval", {}).get("k", (1, 5, 10)))
    scored = [r for r in split_rows if r["uid"] in pred_by_uid]
    pairs = [
        (pred_by_uid[r["uid"]]["ranked_ids"], gold.get(r["uid"], []))
        for r in scored
    ]

    def compute(indices) -> dict[str, Any]:
        return M.retrieval_metrics([pairs[i] for i in indices], ks=ks)

    return compute_with_breakdown(
        scored, cfg["breakdown"], compute, min_cell_n=cfg["min_cell_n"],
    )


def score_transliteration(
    split_rows: list[dict[str, Any]],
    pred_by_uid: dict[str, dict[str, Any]],
    gold: dict[str, list[str]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """CER / WER / exact match against a native-script reference (FR-5).

    Only rows that HAVE a reference are scored; a romanized message nobody
    rewrote in Gurmukhi cannot be marked right or wrong. Those rows are absent
    from the gold file, so `check_coverage` already reports the denominator.
    """
    scored = [r for r in split_rows if r["uid"] in pred_by_uid and r["uid"] in gold]
    hypotheses = [pred_by_uid[r["uid"]]["transliterated"] for r in scored]
    references = [gold[r["uid"]][0] for r in scored]

    def compute(indices) -> dict[str, Any]:
        return M.transliteration_metrics(
            [hypotheses[i] for i in indices], [references[i] for i in indices],
        )

    return compute_with_breakdown(
        scored, cfg["breakdown"], compute, min_cell_n=cfg["min_cell_n"],
    )


def score_span(
    split_rows: list[dict[str, Any]],
    pred_by_uid: dict[str, dict[str, Any]],
    gold: dict[str, list[str]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Token F1 over claim tokens, against a BIO gold sequence (FR-7).

    `O` is deliberately not scored as a class. About half of every X-CLAIM post
    is not the claim, so a model that predicted `O` everywhere would look
    respectable on a three-class average while finding nothing.
    """
    scored = [r for r in split_rows if r["uid"] in pred_by_uid and r["uid"] in gold]
    hypotheses = [list(pred_by_uid[r["uid"]]["bio"]) for r in scored]
    references = [gold[r["uid"]] for r in scored]
    try:
        validate_labels([t for tags in hypotheses for t in tags], "span_bio",
                        where=f"{cfg['predictions']} (predicted)")
    except ValueError as exc:
        raise EvalRefused(str(exc)) from None

    def compute(indices) -> dict[str, Any]:
        try:
            return M.span_metrics([hypotheses[i] for i in indices],
                                  [references[i] for i in indices])
        except ValueError as exc:
            raise EvalRefused(str(exc)) from None

    return compute_with_breakdown(
        scored, cfg["breakdown"], compute, min_cell_n=cfg["min_cell_n"],
    )


def score_normalization(
    split_rows: list[dict[str, Any]],
    pred_by_uid: dict[str, dict[str, Any]],
    gold: dict[str, list[str]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """chrF and exact match against the reference normalized claim (FR-7)."""
    scored = [r for r in split_rows if r["uid"] in pred_by_uid and r["uid"] in gold]
    hypotheses = [pred_by_uid[r["uid"]]["normalized"] for r in scored]
    references = [gold[r["uid"]][0] for r in scored]

    def compute(indices) -> dict[str, Any]:
        return M.normalization_metrics([hypotheses[i] for i in indices],
                                       [references[i] for i in indices])

    return compute_with_breakdown(
        scored, cfg["breakdown"], compute, min_cell_n=cfg["min_cell_n"],
    )


def score(
    task: str,
    split_rows: list[dict[str, Any]],
    pred_by_uid: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
    gold: dict[str, list[str]] | None,
) -> dict[str, Any]:
    if task == "classification":
        return score_classification(split_rows, pred_by_uid, cfg)
    if task == "retrieval":
        assert gold is not None
        return score_retrieval(split_rows, pred_by_uid, gold, cfg)
    if task == "transliteration":
        assert gold is not None
        return score_transliteration(split_rows, pred_by_uid, gold, cfg)
    if task == "span":
        assert gold is not None
        return score_span(split_rows, pred_by_uid, gold, cfg)
    if task == "normalization":
        assert gold is not None
        return score_normalization(split_rows, pred_by_uid, gold, cfg)
    # Unreachable: evaluate() rejects unsupported tasks before reaching here.
    raise EvalRefused(f"no scorer registered for task {task!r}")


def _corpus_ids(cfg: dict[str, Any]) -> list[str]:
    """Every id a retrieval run could have returned, if the config names one.

    `corpus_ids:` points at the id list the index was built from, so the random
    baseline draws from the same population the model searched. Without it a
    "random" ranking is drawn only from correct answers.
    """
    path = cfg.get("corpus_ids")
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        raise EvalRefused(
            f"corpus_ids file not found: {p}. It is what the random baseline "
            "draws from; without it the baseline is not comparable."
        )
    return list(load_json(p)["ids"])


def load_interim_texts(split_path: Path) -> dict[str, str]:
    """uid -> source text, from the gitignored materialised copy.

    Split files hold ids, not text (the Phase 0 decision), so a baseline that
    needs the input itself has to resolve it the same way the batch runner does.
    """
    interim = Path("data/interim") / split_path.parent.name / f"{split_path.stem}.jsonl"
    # Fixtures keep their text beside the split as `texts.jsonl` rather than
    # under data/interim/, so the harness stays testable without a built dataset.
    sibling = split_path.parent / "texts.jsonl"
    path = interim if interim.is_file() else sibling
    if not path.is_file():
        raise EvalRefused(
            f"no materialised text at {interim}, which this baseline needs. "
            "Run `make data` to rebuild data/interim/."
        )
    return {r["uid"]: r["text"] for r in load_jsonl(path)}


def run_baseline(
    cfg: dict[str, Any],
    split_rows: list[dict[str, Any]],
    gold: dict[str, list[str]] | None,
    out_dir: Path,
) -> dict[str, Any]:
    """Score the baseline through the identical path, or load a prior run."""
    name = cfg["baseline"]

    if _HASH_RE.match(name) and not baselines_mod.is_registered(name):
        prior = out_dir / f"{name}.json"
        if not prior.is_file():
            raise EvalRefused(
                f"baseline {name!r} looks like a config_hash but {prior} does not exist."
            )
        doc = load_json(prior)
        return {"name": name, "kind": "prior_run",
                "experiment": doc.get("experiment"),
                "metrics": doc.get("metrics", {}).get("overall", {})}

    fn = baselines_mod.get_baseline(name)
    # The baseline must read gold from the same column the model is scored
    # against, or it answers a different question than the one being asked.
    kwargs: dict[str, Any] = {"seed": cfg["seed"],
                              "gold_field": cfg.get("gold_field", "label")}
    notes: list[str] = []
    if name in ("identity_transliteration", "longest_sentence"):
        kwargs["texts"] = load_interim_texts(Path(cfg["split"]))
    if name == "whole_post_span":
        # It needs the token count per row, which only the gold carries.
        kwargs["gold"] = gold
    if name == "random_rank":
        # Prefer the REAL corpus when the run names one. Sampling from the gold
        # documents alone would draw every candidate from the set of things that
        # are somebody's correct answer, which is a far easier lottery than the
        # retriever faces and would overstate the floor it has to beat.
        pool = _corpus_ids(cfg) or sorted(
            {doc for ids in (gold or {}).values() for doc in ids}
        )
        kwargs["candidate_ids"] = pool
        depth = max(cfg.get("metrics", {}).get("retrieval", {}).get("k", [10]))
        if len(pool) <= depth * 2:
            notes.append(
                f"random_rank drew from a pool of only {len(pool)} documents while "
                f"scoring up to rank {depth}, so it retrieves most of the corpus by "
                "construction and its Recall@k is near 1.0. That is a degenerate "
                "floor, not a strong baseline. Build the candidate pool from the full "
                "retrieval corpus, not just the gold documents."
            )
    rows = fn(split_rows, **kwargs)
    pred_by_uid = {r["uid"]: r for r in rows}
    scored = score(cfg["task"], split_rows, pred_by_uid, cfg, gold)
    return {"name": name, "kind": "generated", "metrics": scored["overall"], "notes": notes}


def delta_vs_baseline(model: dict[str, Any], base: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in model.items():
        if not isinstance(value, (int, float)) or key in {"n", "n_skipped_no_relevant"}:
            continue
        other = base.get(key)
        if isinstance(other, (int, float)):
            out[key] = float(value) - float(other)
    return out


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def evaluate(config_path: str | Path, out_dir: str | Path = DEFAULT_OUT_DIR,
             schema_path: str | Path = SCHEMA_PATH) -> dict[str, Any]:
    cfg = load_config(config_path, schema_path)
    seeded = set_all_seeds(cfg["seed"])

    guard_baseline(cfg)

    if cfg["task"] == "faithfulness":
        raise EvalRefused(
            "task 'faithfulness' arrives in Phase 6 with NLI-based entailment "
            "scoring (docs/build-plan.md, 'Phase 6')."
        )

    split_path = Path(cfg["split"])
    if not split_path.is_file():
        raise EvalRefused(f"split not found: {split_path}")

    # Integrity BEFORE parsing. A tampered split must be reported as a broken
    # freeze, not as whatever parse error the tampering happens to produce.
    split_sha, lock_sha = guard_split_frozen(split_path)
    try:
        split_rows = load_split(split_path)
    except (JsonlError, SplitError) as exc:
        raise EvalRefused(f"{split_path} is not a valid split file: {exc}") from None
    guard_test_split(split_path, split_rows)

    pred_path = Path(cfg["predictions"])
    pred_by_uid = load_predictions(pred_path, cfg["task"])
    pred_sha = sha256_file(pred_path)

    needs_gold = cfg["task"] in ("retrieval", "transliteration", "span", "normalization")
    gold = load_gold_retrieval(cfg["gold"]) if needs_gold else None

    # Transliteration gold covers only the rows somebody wrote a reference for --
    # 33 of the 100 hand-typed forwards. Requiring a prediction for every split
    # row would refuse a run that is complete; requiring one for every GOLD row
    # is the check that actually matters.
    # These tasks' gold covers only the rows somebody annotated, so the split is
    # the universe of what MAY be predicted and the gold is what MUST be.
    partial_gold = cfg["task"] in ("transliteration", "span", "normalization")
    expected_uids = (sorted(gold) if partial_gold
                     else [r["uid"] for r in split_rows])
    coverage = check_coverage(
        expected_uids, pred_by_uid,
        allow_partial=cfg["allow_partial"],
        universe={r["uid"] for r in split_rows},
    )

    scored = score(cfg["task"], split_rows, pred_by_uid, cfg, gold)
    base = run_baseline(cfg, split_rows, gold, Path(out_dir))

    warnings = collect_sanity_warnings(scored, cfg["sanity_ceiling"])
    warnings.extend(base.get("notes", []))
    if lock_sha is None:
        warnings.append(
            f"{split_path} is not covered by a SPLITS.lock, so its contents were not "
            "verified. Acceptable for a fixture; not acceptable for a reported number."
        )
    git = git_info()
    if git.get("dirty"):
        warnings.append(
            "Working tree was DIRTY at eval time: the committed code does not "
            "reproduce this number."
        )

    headline = {"classification": "macro_f1", "retrieval": "mrr",
                "transliteration": "cer", "span": "token_f1",
                "normalization": "chrf"}[cfg["task"]]
    # The native-vs-romanized gap needs a metric that MEANS something inside one
    # cell. For language identification it cannot be macro-F1: the cells are
    # split by language and the classes ARE languages, so every cell holds a
    # single gold class and its macro-F1 is pinned at 1/n_classes no matter how
    # right or wrong the model is. Per-cell accuracy is the honest measure there.
    gap_metric = "accuracy" if cfg.get("gold_field") == "lang" else headline
    # `script_gap` subtracts romanized from native, which only reads as "native
    # is better" for a higher-is-better metric. Transliteration gold exists only
    # for romanized rows, so there is no native cell and the gap would be noise.
    gaps = ({} if cfg["task"] == "transliteration"
            else script_gap(scored.get("by", {}), gap_metric))

    config_hash = sha256_bytes(
        canonical_json(cfg) + pred_sha.encode() + (lock_sha or "nolock").encode()
    )[:CONFIG_HASH_LEN]

    doc: dict[str, Any] = {
        "config_hash": config_hash,
        "experiment": cfg["experiment"],
        "task": cfg["task"],
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git,
        "env": env_info(),
        "seed": cfg["seed"],
        "seeded_libraries": seeded,
        "inputs": {
            "config": cfg,
            "config_path": Path(config_path).as_posix(),
            "split_path": split_path.as_posix(),
            "split_sha256": split_sha,
            "splits_lock_sha256": lock_sha,
            "predictions_path": pred_path.as_posix(),
            "predictions_sha256": pred_sha,
        },
        "coverage": coverage,
        "metrics": scored,
        "native_vs_romanized": {"metric": gap_metric, "by_lang": gaps},
        "baseline": base,
        "delta_vs_baseline": delta_vs_baseline(scored["overall"], base["metrics"]),
        "warnings": warnings,
    }

    out_path = Path(out_dir) / f"{config_hash}.json"
    write_json(out_path, doc)
    doc["_written_to"] = out_path.as_posix()
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.evaluate",
        description="Score a predictions JSONL against a frozen split. "
                    "The only place metrics are computed.",
    )
    parser.add_argument("--config", required=True, help="path to the experiment YAML")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="results directory")
    parser.add_argument("--schema", default=str(SCHEMA_PATH))
    args = parser.parse_args(argv)

    try:
        doc = evaluate(args.config, args.out, args.schema)
    except EvalRefused as exc:
        print(f"\nREFUSED: {exc}\n", file=sys.stderr)
        return 2

    headline = doc["metrics"]["overall"]
    print(f"\n{doc['experiment']}  [{doc['config_hash']}]  task={doc['task']}")
    print(f"  written  : {doc['_written_to']}")
    # Scored / required, not predicted / required. A transliteration run
    # predicts on all 100 split rows while only 33 carry a reference, and
    # "100/33" reads like over-coverage when it is in fact complete.
    cov = doc["coverage"]
    scored = cov["n_gold"] - cov["n_missing"]
    extra = (f"  ({cov['n_predicted']} predicted)"
             if cov["n_predicted"] != cov["n_gold"] else "")
    print(f"  coverage : {scored}/{cov['n_gold']} scored{extra}")
    base_name = doc["baseline"]["name"]
    for key, value in sorted(headline.items()):
        if not isinstance(value, (int, float)) or key in {"n", "n_skipped_no_relevant"}:
            continue
        delta = doc["delta_vs_baseline"].get(key)
        if delta is None:
            print(f"  {key:<20} {value:.4f}")
        else:
            print(f"  {key:<20} {value:.4f}   "
                  f"[{base_name} {value - delta:.4f}, delta {delta:+.4f}]")

    low_n = [name for name, cell in doc["metrics"].get("by", {}).items() if cell.get("low_n")]
    if low_n:
        print(f"  {len(low_n)} of {len(doc['metrics'].get('by', {}))} cells below "
              f"min_cell_n: {', '.join(low_n)}")
    for warning in doc["warnings"]:
        print(f"\n  ! {warning}", file=sys.stderr)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
