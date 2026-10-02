"""The report-number checker: a figure attributed to a run must be in that run."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path("scripts/check_report_numbers.py")


@pytest.fixture
def checker(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("check_report_numbers", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "aaaaaaaaaaaa.json").write_text(json.dumps(
        {"metrics": {"overall": {"macro_f1": 0.28022671, "ece": 0.0689}},
         "paired_vs_baseline": {"delta": -0.0291}}), encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    mod._cache.clear()
    return mod


def test_a_number_that_is_in_its_run_passes(checker):
    assert checker.check("macro-F1 0.2802 (run aaaaaaaaaaaa) on dev") == []


def test_a_mislabelled_number_is_caught(checker):
    problems = checker.check("macro-F1 0.2949 (run aaaaaaaaaaaa)")
    assert problems and "0.2949" in problems[0]


def test_a_missing_run_is_caught(checker):
    assert "no results file" in checker.check("0.5 (run bbbbbbbbbbbb)")[0]


def test_sign_is_ignored_and_precision_follows_the_quote(checker):
    assert checker.check("a delta of -0.029 (run aaaaaaaaaaaa)") == []
    assert checker.check("ECE 0.07 (run aaaaaaaaaaaa)") == []


def test_table_rows_are_checked_against_their_one_run(checker):
    assert checker.check("| served | 0.2802 | 0.0689 | aaaaaaaaaaaa |") == []
    assert checker.check("| served | 0.3000 | aaaaaaaaaaaa |")
