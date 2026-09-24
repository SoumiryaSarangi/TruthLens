"""End-to-end tests for the eval harness, and for each guardrail that makes it
refuse.

The refusal tests are the point. A harness that produces a number is easy; a
harness that declines to produce a number it cannot stand behind is the whole
reason Phase 0 exists.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from common.io_jsonl import load_jsonl
from eval.evaluate import EvalRefused, evaluate, main

BASE_CONFIG = Path("configs/example_majority_baseline.yaml")
RETRIEVAL_CONFIG = Path("configs/example_retrieval_baseline.yaml")


def write_config(tmp_path: Path, **overrides) -> Path:
    """Copy the example config, apply overrides, drop keys whose value is None."""
    cfg = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    for key, value in overrides.items():
        if value is None:
            cfg.pop(key, None)
        else:
            cfg[key] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


# -----------------------------------------------------------------------------
# The happy path
# -----------------------------------------------------------------------------


def test_classification_run_writes_a_results_json(tmp_path):
    doc = evaluate(BASE_CONFIG, tmp_path)
    written = Path(doc["_written_to"])
    assert written.is_file()
    assert written.name == f"{doc['config_hash']}.json"


def test_results_json_has_everything_needed_to_reproduce_it(tmp_path):
    doc = evaluate(BASE_CONFIG, tmp_path)
    for key in ("config_hash", "experiment", "created_utc", "git", "env", "seed",
                "inputs", "coverage", "metrics", "baseline", "delta_vs_baseline",
                "warnings"):
        assert key in doc, f"results JSON is missing {key!r}"
    assert doc["inputs"]["predictions_sha256"]
    assert doc["inputs"]["split_sha256"]
    assert doc["env"]["python"].startswith("3.11")
    assert doc["seed"] == 42


def test_metrics_are_broken_down_by_language_and_script(tmp_path):
    doc = evaluate(BASE_CONFIG, tmp_path)
    cells = doc["metrics"]["by"]
    assert "lang=hi,script=deva" in cells
    assert "lang=hi,script=latn" in cells
    assert "lang=pa,script=guru" in cells


def test_small_cells_are_flagged_rather_than_hidden(tmp_path):
    doc = evaluate(BASE_CONFIG, tmp_path)
    cells = doc["metrics"]["by"]
    assert all(cell.get("low_n") for cell in cells.values()), \
        "nine fixture rows means every cell should be flagged low_n"
    assert all("macro_f1" in cell for cell in cells.values()), \
        "a low_n cell must still report its number, not hide it"


def test_baseline_is_scored_through_the_same_path(tmp_path):
    doc = evaluate(BASE_CONFIG, tmp_path)
    assert doc["baseline"]["name"] == "majority_class"
    assert doc["baseline"]["kind"] == "generated"
    assert "macro_f1" in doc["baseline"]["metrics"]
    expected = doc["metrics"]["overall"]["macro_f1"] - doc["baseline"]["metrics"]["macro_f1"]
    assert doc["delta_vs_baseline"]["macro_f1"] == pytest.approx(expected)


def test_native_vs_romanized_gap_is_computed(tmp_path):
    """The research contribution, reported by the harness rather than by hand."""
    doc = evaluate(BASE_CONFIG, tmp_path)
    gaps = doc["native_vs_romanized"]["by_lang"]
    assert "gap" in gaps["hi"]
    assert gaps["hi"]["gap"] == pytest.approx(
        gaps["hi"]["native"] - gaps["hi"]["romanized"]
    )


def test_retrieval_task_runs_and_reports_its_own_metric_family(tmp_path):
    doc = evaluate(RETRIEVAL_CONFIG, tmp_path)
    overall = doc["metrics"]["overall"]
    for metric in ("mrr", "recall@1", "recall@10", "success@10"):
        assert metric in overall


def test_config_hash_is_stable_and_input_sensitive(tmp_path):
    first = evaluate(BASE_CONFIG, tmp_path)["config_hash"]
    second = evaluate(BASE_CONFIG, tmp_path)["config_hash"]
    assert first == second

    other = evaluate(write_config(tmp_path, experiment="renamed"), tmp_path)
    assert other["config_hash"] != first, "a changed config must not reuse a results file"


def test_cli_returns_zero_on_success(tmp_path):
    assert main(["--config", str(BASE_CONFIG), "--out", str(tmp_path)]) == 0


# -----------------------------------------------------------------------------
# Guardrail 1: no baseline, no result
# -----------------------------------------------------------------------------


def test_refuses_without_a_baseline(tmp_path):
    cfg = write_config(tmp_path, baseline=None)
    with pytest.raises(EvalRefused, match="baseline"):
        evaluate(cfg, tmp_path)
    assert not list(tmp_path.glob("*.json")), "a refused run must not write a results file"


def test_refuses_an_unregistered_baseline(tmp_path):
    cfg = write_config(tmp_path, baseline="wishful_thinking")
    with pytest.raises(EvalRefused, match="registered baseline"):
        evaluate(cfg, tmp_path)


# -----------------------------------------------------------------------------
# Guardrail 2: the test set is not for model selection
# -----------------------------------------------------------------------------


def test_refuses_a_test_split_by_default(tmp_path, no_test_split_override):
    cfg = write_config(tmp_path, split="tests/fixtures/toy_clean/test.jsonl",
                       allow_partial=True)
    with pytest.raises(EvalRefused, match="TEST split"):
        evaluate(cfg, tmp_path)


def test_allows_a_test_split_when_explicitly_unlocked(tmp_path, allow_test_split):
    cfg = write_config(tmp_path, split="tests/fixtures/toy_clean/test.jsonl",
                       allow_partial=True)
    # Predictions cover dev, not test, so this must fail on coverage -- proving
    # the run got PAST the test-split guard rather than being blocked by it.
    with pytest.raises(EvalRefused, match="not in the split"):
        evaluate(cfg, tmp_path)


# -----------------------------------------------------------------------------
# Guardrail 3: frozen splits
# -----------------------------------------------------------------------------


def test_refuses_a_split_that_does_not_match_the_lock(tmp_path):
    work = tmp_path / "fixtures"
    shutil.copytree("tests/fixtures", work)
    victim = work / "toy_clean" / "dev.jsonl"
    with victim.open("ab") as fh:
        fh.write(b"\n")

    cfg = write_config(tmp_path, split=str(victim).replace("\\", "/"),
                       predictions="tests/fixtures/toy_clean/predictions_demo.jsonl")
    with pytest.raises(EvalRefused, match="does not match"):
        evaluate(cfg, tmp_path)


def test_refuses_a_split_absent_from_the_lock(tmp_path):
    work = tmp_path / "fixtures"
    shutil.copytree("tests/fixtures", work)
    stray = work / "toy_clean" / "dev.jsonl"
    stray.rename(work / "toy_clean" / "unlocked.jsonl")

    cfg = write_config(tmp_path,
                       split=str(work / "toy_clean" / "unlocked.jsonl").replace("\\", "/"))
    with pytest.raises(EvalRefused, match="not listed in"):
        evaluate(cfg, tmp_path)


# -----------------------------------------------------------------------------
# Guardrail 4: suspiciously high numbers
# -----------------------------------------------------------------------------


def test_warns_when_a_metric_exceeds_the_sanity_ceiling(tmp_path):
    cfg = write_config(tmp_path, sanity_ceiling=0.1)
    doc = evaluate(cfg, tmp_path)
    assert any("SUSPICIOUSLY HIGH" in w for w in doc["warnings"])
    assert any("47-50%" in w for w in doc["warnings"])


def test_no_sanity_warning_at_the_default_ceiling(tmp_path):
    doc = evaluate(BASE_CONFIG, tmp_path)
    assert not any("SUSPICIOUSLY HIGH" in w for w in doc["warnings"])


# -----------------------------------------------------------------------------
# Guardrail 5: coverage
# -----------------------------------------------------------------------------


def test_refuses_predictions_for_rows_outside_the_split(tmp_path):
    preds = tmp_path / "preds.jsonl"
    original = Path("tests/fixtures/toy_clean/predictions_demo.jsonl").read_text("utf-8")
    preds.write_text(original + '{"uid":"not-in-the-split","pred":"NEI"}\n', encoding="utf-8")

    cfg = write_config(tmp_path, predictions=str(preds).replace("\\", "/"))
    with pytest.raises(EvalRefused, match="not in the split"):
        evaluate(cfg, tmp_path)


def test_refuses_incomplete_predictions_unless_allowed(tmp_path):
    preds = tmp_path / "partial.jsonl"
    lines = Path("tests/fixtures/toy_clean/predictions_demo.jsonl").read_text(
        "utf-8").splitlines(keepends=True)
    preds.write_text("".join(lines[:5]), encoding="utf-8")

    cfg = write_config(tmp_path, predictions=str(preds).replace("\\", "/"))
    with pytest.raises(EvalRefused, match="no prediction"):
        evaluate(cfg, tmp_path)

    doc = evaluate(write_config(tmp_path, predictions=str(preds).replace("\\", "/"),
                                allow_partial=True), tmp_path)
    assert doc["coverage"]["n_missing"] == 4
    assert doc["coverage"]["coverage"] == pytest.approx(5 / 9)


def test_refuses_duplicate_prediction_rows(tmp_path):
    preds = tmp_path / "dupes.jsonl"
    lines = Path("tests/fixtures/toy_clean/predictions_demo.jsonl").read_text(
        "utf-8").splitlines(keepends=True)
    preds.write_text("".join(lines) + lines[0], encoding="utf-8")

    cfg = write_config(tmp_path, predictions=str(preds).replace("\\", "/"))
    with pytest.raises(EvalRefused, match="duplicate uid"):
        evaluate(cfg, tmp_path)


# -----------------------------------------------------------------------------
# Config validation
# -----------------------------------------------------------------------------


def test_refuses_an_unknown_config_key(tmp_path):
    """A typo'd key must fail, not be ignored."""
    cfg = write_config(tmp_path, learning_rate=0.001)
    with pytest.raises(EvalRefused, match="invalid config"):
        evaluate(cfg, tmp_path)


def test_refuses_an_unknown_label(tmp_path):
    preds = tmp_path / "badlabel.jsonl"
    preds.write_text(
        "\n".join(
            f'{{"uid":"toy_clean:{lang}:dev:{i:04d}","pred":"Refutd"}}'
            for i, lang in enumerate(
                ["en", "en", "en", "en", "hi", "hi", "hi", "pa", "pa"])
        ) + "\n",
        encoding="utf-8",
    )
    cfg = write_config(tmp_path, predictions=str(preds).replace("\\", "/"))
    with pytest.raises(EvalRefused, match="not in label set"):
        evaluate(cfg, tmp_path)


def test_refuses_a_missing_config(tmp_path):
    with pytest.raises(EvalRefused, match="config not found"):
        evaluate(tmp_path / "nope.yaml", tmp_path)


def test_faithfulness_task_is_registered_but_not_yet_implemented(tmp_path):
    cfg = write_config(tmp_path, task="faithfulness")
    with pytest.raises(EvalRefused, match="Phase 6"):
        evaluate(cfg, tmp_path)


def test_cli_returns_two_on_refusal(tmp_path):
    cfg = write_config(tmp_path, baseline=None)
    assert main(["--config", str(cfg), "--out", str(tmp_path)]) == 2


# -----------------------------------------------------------------------------
# gold_field: scoring against a split column other than `label` (FR-3)
# -----------------------------------------------------------------------------


def test_gold_field_scores_against_the_language_column(tmp_path):
    """Language ID gold is the language each row already declares.

    Without this the only way to measure FR-3 would be a purpose-built split,
    which would mean measuring it on 100 rows instead of every dataset we have.
    """
    preds = tmp_path / "lang_preds.jsonl"
    rows = load_jsonl(Path("tests/fixtures/toy_clean/dev.jsonl"))
    preds.write_text(
        "".join(json.dumps({"uid": r["uid"], "pred": r["lang"]}) + "\n" for r in rows),
        encoding="utf-8",
    )
    cfg = write_config(
        tmp_path, predictions=str(preds).replace("\\", "/"),
        gold_field="lang", label_set="lang_4class", baseline="majority_class",
    )
    doc = evaluate(cfg, tmp_path)
    assert doc["metrics"]["overall"]["accuracy"] == 1.0


def test_gold_field_also_moves_the_baseline(tmp_path):
    """The bug this pins: a baseline reading `label` while scored on `lang`.

    It predicted the majority VERDICT against LANGUAGE gold. The harness caught
    it only because the two label sets happen to be disjoint -- if the split had
    ever held a label called `en` it would have scored silently and wrongly.
    """
    preds = tmp_path / "lang_preds.jsonl"
    rows = load_jsonl(Path("tests/fixtures/toy_clean/dev.jsonl"))
    preds.write_text(
        "".join(json.dumps({"uid": r["uid"], "pred": r["lang"]}) + "\n" for r in rows),
        encoding="utf-8",
    )
    cfg = write_config(
        tmp_path, predictions=str(preds).replace("\\", "/"),
        gold_field="lang", label_set="lang_4class", baseline="majority_class",
    )
    doc = evaluate(cfg, tmp_path)
    assert doc["baseline"]["kind"] == "generated"
    assert "accuracy" in doc["baseline"]["metrics"]


def test_an_unknown_gold_field_is_refused(tmp_path):
    cfg = write_config(tmp_path, gold_field="not_a_column")
    with pytest.raises(EvalRefused, match="invalid config"):
        evaluate(cfg, tmp_path)


# -----------------------------------------------------------------------------
# task: transliteration (FR-5)
# -----------------------------------------------------------------------------


def _translit_setup(tmp_path: Path, hypothesis: str):
    """A one-row transliteration task against the toy fixture."""
    rows = load_jsonl(Path("tests/fixtures/toy_clean/dev.jsonl"))
    uid = rows[0]["uid"]
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps({"uid": uid, "reference": "abcd"}) + "\n", encoding="utf-8")
    preds = tmp_path / "preds.jsonl"
    preds.write_text(
        json.dumps({"uid": uid, "transliterated": hypothesis}) + "\n", encoding="utf-8",
    )
    return gold, preds


def test_transliteration_scores_cer_wer_and_exact_match(tmp_path):
    gold, preds = _translit_setup(tmp_path, "abcd")
    cfg = write_config(
        tmp_path, task="transliteration", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="identity_transliteration",
    )
    doc = evaluate(cfg, tmp_path)
    overall = doc["metrics"]["overall"]
    assert overall["cer"] == 0.0
    assert overall["wer"] == 0.0
    assert overall["exact_match"] == 1.0


def test_transliteration_gold_may_cover_only_some_split_rows(tmp_path):
    """33 of 100 hand-typed forwards carry a Gurmukhi reference.

    Predicting on all 100 is correct and must not be reported as 67 stray uids;
    failing to predict one of the 33 still has to be caught.
    """
    gold, _ = _translit_setup(tmp_path, "abcd")
    rows = load_jsonl(Path("tests/fixtures/toy_clean/dev.jsonl"))
    preds = tmp_path / "all_preds.jsonl"
    preds.write_text(
        "".join(json.dumps({"uid": r["uid"], "transliterated": "abcd"}) + "\n" for r in rows),
        encoding="utf-8",
    )
    cfg = write_config(
        tmp_path, task="transliteration", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="identity_transliteration",
    )
    doc = evaluate(cfg, tmp_path)
    assert doc["coverage"]["n_gold"] == 1
    assert doc["coverage"]["n_missing"] == 0
    assert doc["coverage"]["n_predicted"] == len(rows)


def test_transliteration_still_refuses_a_uid_outside_the_split(tmp_path):
    gold, _ = _translit_setup(tmp_path, "abcd")
    preds = tmp_path / "bad_preds.jsonl"
    preds.write_text(
        json.dumps({"uid": "not-in-the-split", "transliterated": "abcd"}) + "\n",
        encoding="utf-8",
    )
    cfg = write_config(
        tmp_path, task="transliteration", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="identity_transliteration",
    )
    with pytest.raises(EvalRefused, match="not in the split"):
        evaluate(cfg, tmp_path)


def test_error_rates_do_not_trip_the_sanity_ceiling(tmp_path):
    """CER above 0.85 is a bad transliterator, not a suspicious result.

    Warning on it would train the reader to ignore this warning, which is the
    one that catches leakage.
    """
    gold, preds = _translit_setup(tmp_path, "zzzzzzzzzz")
    cfg = write_config(
        tmp_path, task="transliteration", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="identity_transliteration",
    )
    doc = evaluate(cfg, tmp_path)
    assert doc["metrics"]["overall"]["cer"] > 0.85
    assert not [w for w in doc["warnings"] if "SUSPICIOUSLY HIGH" in w]


def test_transliteration_gold_needs_a_reference_field(tmp_path):
    rows = load_jsonl(Path("tests/fixtures/toy_clean/dev.jsonl"))
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps({"uid": rows[0]["uid"]}) + "\n", encoding="utf-8")
    preds = tmp_path / "preds.jsonl"
    preds.write_text(
        json.dumps({"uid": rows[0]["uid"], "transliterated": "x"}) + "\n", encoding="utf-8",
    )
    cfg = write_config(
        tmp_path, task="transliteration", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="identity_transliteration",
    )
    with pytest.raises(EvalRefused, match=r"relevant_ids.*reference"):
        evaluate(cfg, tmp_path)


# -----------------------------------------------------------------------------
# task: fast_path (FR-8)
# -----------------------------------------------------------------------------


def _fastpath_setup(tmp_path: Path, scores=None, top_correct=None, gold_ids=None):
    """Nine toy rows: top-1 scores 0.9 down to 0.1, right at 0, 1, 2 and 4.

    Each row returns two candidates, the runner-up scoring 0.05 less, so the
    derived "best non-gold" candidate is the runner-up where the top-1 is right
    and the top-1 itself where it is wrong.
    """
    rows = load_jsonl(Path("tests/fixtures/toy_clean/dev.jsonl"))
    scores = scores or [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    top_correct = top_correct or [True, True, True, False, True,
                                  False, False, False, False]
    gold_path = tmp_path / "gold.jsonl"
    preds_path = tmp_path / "preds.jsonl"
    gold_lines, pred_lines = [], []
    for i, (row, score, ok) in enumerate(zip(rows, scores, top_correct, strict=True)):
        right, wrong = f"doc-{i:03}", f"doc-{i + 900:03}"
        ids = gold_ids[i] if gold_ids is not None else [right]
        gold_lines.append(json.dumps({"uid": row["uid"], "relevant_ids": ids}))
        ranked = [right, wrong] if ok else [wrong, right]
        pred_lines.append(json.dumps({"uid": row["uid"], "ranked_ids": ranked,
                                      "scores": [score, round(score - 0.05, 2)]}))
    gold_path.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    preds_path.write_text("\n".join(pred_lines) + "\n", encoding="utf-8")
    return gold_path, preds_path


def _fastpath_config(tmp_path: Path, gold: Path, preds: Path, **settings):
    return write_config(
        tmp_path, task="fast_path", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="always_match",
        metrics={"fast_path": {"tau": settings.pop("tau", 0.55), **settings}},
    )


def test_fast_path_scores_coverage_precision_and_false_accepts(tmp_path):
    """At tau=0.55 four of nine are accepted and three of those are right."""
    gold, preds = _fastpath_setup(tmp_path)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=0.55), tmp_path)
    overall = doc["metrics"]["overall"]
    assert overall["fastpath_coverage"] == pytest.approx(4 / 9)
    assert overall["fastpath_precision"] == pytest.approx(3 / 4)
    assert overall["fastpath_yield"] == pytest.approx(1 / 3)
    assert overall["false_accept_rate"] == pytest.approx(4 / 9)
    assert overall["tau"] == 0.55


def test_fast_path_reuses_a_retrieval_predictions_file_unchanged(tmp_path):
    """One batch run, two tasks -- the whole point of the seam.

    The committed retrieval fixture is scored as a gate with no edits, which is
    what lets the Phase 4 config reuse the Phase 2 predictions and cost zero
    inference.
    """
    cfg = write_config(
        tmp_path, task="fast_path", label_set=None,
        gold="tests/fixtures/toy_clean/gold_retrieval_dev.jsonl",
        predictions="tests/fixtures/toy_clean/predictions_retrieval_demo.jsonl",
        baseline="always_match",
        metrics={"fast_path": {"tau": 0.5}},
    )
    doc = evaluate(cfg, tmp_path)
    assert doc["metrics"]["overall"]["n"] == 9.0
    assert doc["metrics"]["overall"]["fastpath_coverage"] == 1.0


def test_always_match_is_the_gate_removed(tmp_path):
    """Its coverage and false-accept rate are fixed by construction."""
    gold, preds = _fastpath_setup(tmp_path)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=0.55), tmp_path)
    base = doc["baseline"]["metrics"]
    assert base["fastpath_coverage"] == 1.0
    assert base["false_accept_rate"] == 1.0
    assert base["fastpath_precision"] == pytest.approx(4 / 9)   # == Success@1


def test_always_match_survives_a_retriever_on_another_score_scale(tmp_path):
    """BM25 scores are unbounded; the first version of this baseline used a
    literal 1.0 and so accepted NOTHING on a BM25 tau of 80, reporting coverage
    0.0000 where "the gate removed" must report 1.0. The constant has to come
    from the run."""
    gold, preds = _fastpath_setup(
        tmp_path, scores=[900, 800, 700, 600, 500, 400, 300, 200, 100])
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=550,
                                    taus=[100, 550, 900]), tmp_path)
    base = doc["baseline"]["metrics"]
    assert base["fastpath_coverage"] == 1.0
    assert base["false_accept_rate"] == 1.0
    assert base["fastpath_precision"] == pytest.approx(4 / 9)
    # And the model itself is gated normally on that scale.
    assert doc["metrics"]["overall"]["fastpath_coverage"] == pytest.approx(4 / 9)


def test_the_headline_is_aucc_and_the_curve_is_not_a_metric(tmp_path):
    """`curve` is the result; `tau` and the counts are parameters, not scores.

    None of them may appear in delta_vs_baseline or trip the sanity ceiling --
    n_accepted is a row count and would fire "SUSPICIOUSLY HIGH" on every run.
    """
    gold, preds = _fastpath_setup(tmp_path)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=0.55), tmp_path)
    assert "fastpath_aucc" in doc["delta_vs_baseline"]
    for key in ("curve", "coverage_curve", "tau", "n", "n_accepted", "n_negatives"):
        assert key not in doc["delta_vs_baseline"], key
    assert not any("SUSPICIOUSLY" in w for w in doc["warnings"])
    assert doc["metrics"]["overall"]["curve"][0]["tau"] == 0.55


def test_a_config_without_tau_is_refused(tmp_path):
    """FR-14: the operating point is recorded, never defaulted."""
    gold, preds = _fastpath_setup(tmp_path)
    cfg = write_config(
        tmp_path, task="fast_path", label_set=None,
        gold=str(gold).replace("\\", "/"), predictions=str(preds).replace("\\", "/"),
        baseline="always_match", metrics={"fast_path": {"taus": [0.6]}},
    )
    with pytest.raises(EvalRefused):
        evaluate(cfg, tmp_path)


def test_misaligned_scores_are_refused(tmp_path):
    gold, preds = _fastpath_setup(tmp_path)
    rows = [json.loads(line) for line in preds.read_text(encoding="utf-8").splitlines()]
    rows[0]["scores"] = rows[0]["scores"][:1]
    preds.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(EvalRefused, match="score"):
        evaluate(_fastpath_config(tmp_path, gold, preds), tmp_path)


def test_scores_not_ranked_best_first_are_refused(tmp_path):
    """tau gates scores[0]. If that is not the maximum, tau gates nothing."""
    gold, preds = _fastpath_setup(tmp_path)
    rows = [json.loads(line) for line in preds.read_text(encoding="utf-8").splitlines()]
    rows[0]["scores"] = [0.1, 0.9]
    preds.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(EvalRefused, match="best-first"):
        evaluate(_fastpath_config(tmp_path, gold, preds), tmp_path)


def test_predictions_without_scores_are_refused(tmp_path):
    """`scores` is conventional for retrieval and load-bearing here."""
    gold, preds = _fastpath_setup(tmp_path)
    rows = [json.loads(line) for line in preds.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row.pop("scores")
    preds.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(EvalRefused, match="scores"):
        evaluate(_fastpath_config(tmp_path, gold, preds), tmp_path)


def test_a_tau_above_every_score_warns_rather_than_reporting_a_silent_zero(tmp_path):
    """The error waiting to happen once BM25's unbounded scores share this task."""
    gold, preds = _fastpath_setup(tmp_path)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=99.0), tmp_path)
    assert any("never fires" in w for w in doc["warnings"])


def test_a_tau_below_every_score_warns_that_it_is_measuring_success_at_1(tmp_path):
    gold, preds = _fastpath_setup(tmp_path)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=-1.0), tmp_path)
    assert any("never declines" in w for w in doc["warnings"])


def test_a_query_with_no_correct_answer_scores_on_the_negative_arm_only(tmp_path):
    """An empty `relevant_ids` is a natural negative, not a guaranteed miss."""
    gold_ids = [[f"doc-{i:03}"] for i in range(9)]
    gold_ids[0] = []
    gold, preds = _fastpath_setup(tmp_path, gold_ids=gold_ids)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds, tau=0.55), tmp_path)
    overall = doc["metrics"]["overall"]
    assert overall["n"] == 8.0
    assert overall["n_natural_negatives"] == 1.0


def test_fast_path_metrics_are_broken_down_by_script(tmp_path):
    """The gate is where romanization bites hardest: a romanized query's cosine
    is depressed, so one global tau may not be defensible across scripts."""
    gold, preds = _fastpath_setup(tmp_path)
    doc = evaluate(_fastpath_config(tmp_path, gold, preds), tmp_path)
    assert "fastpath_aucc" in doc["metrics"]["by"]["lang=hi,script=latn"]
