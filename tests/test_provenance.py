"""Run provenance, and one guardrail that had never once been informative.

`dirty: true` in a results file is supposed to mean "the committed code does not
reproduce this number". It was computed from `git status --porcelain` with no
exclusions, so writing one results file made the tree dirty for the next eval in
the same batch -- and **all 31 results files in the repo carried the flag**.
`docs/results.md` printed "dirty tree" in the Flags column of every row, which
teaches a reader to ignore the column.

These tests pin the distinction: results are outputs and do not count, source
files are inputs and do.
"""

from __future__ import annotations

import pytest

from common.provenance import _status_paths, git_info


@pytest.mark.parametrize("status, expected", [
    ("", []),
    (" M src/eval/evaluate.py", ["src/eval/evaluate.py"]),
    # `_git` strips its whole stdout, so the FIRST line of an unstaged change
    # arrives without its leading space. Slicing a fixed offset turned
    # "M results/x.json" into "esults/x.json", which matched no exclusion and
    # reported the run dirty -- the one case the exclusion exists for.
    ("M results/x.json", ["results/x.json"]),
    ("M results/x.json\n?? results/y.json", ["results/x.json", "results/y.json"]),
    ("?? results/abc123.json", ["results/abc123.json"]),
    ("D  results/old.json\n M docs/results.md",
     ["results/old.json", "docs/results.md"]),
    # A rename reports both sides; the destination is the file that now exists.
    ('R  src/a.py -> src/b.py', ["src/b.py"]),
    # Windows paths and quoting, both of which `--porcelain` can emit.
    ('?? "results/a b.json"', ["results/a b.json"]),
])
def test_status_paths(status, expected):
    assert _status_paths(status) == expected


def _dirty(monkeypatch, status: str):
    """git_info with a canned `git status --porcelain`."""
    def fake(*args, **kwargs):
        return status if args[0] == "status" else "sha"
    monkeypatch.setattr("common.provenance._git", fake)
    return git_info()["dirty"]


def test_an_uncommitted_results_file_is_not_dirtiness(monkeypatch):
    """The whole point. Writing results cannot change what a run computed."""
    assert _dirty(monkeypatch, "?? results/34bd7770cb7f.json") is False
    assert _dirty(monkeypatch, "?? results/a.json\n M results/b.json") is False
    # The stripped-first-line form, which is what `_git` actually returns.
    assert _dirty(monkeypatch, "M results/b.json\n?? results/a.json") is False


def test_uncommitted_source_is_still_dirtiness(monkeypatch):
    """Including UNTRACKED source: a new module the run imported is exactly the
    thing that stops a committed tree from reproducing a number."""
    assert _dirty(monkeypatch, " M src/eval/evaluate.py") is True
    assert _dirty(monkeypatch, "?? src/claims/nli_zeroshot.py") is True
    assert _dirty(monkeypatch, " M configs/p3_cw_handtyped_nli.yaml") is True


def test_source_changes_are_not_masked_by_results_changes(monkeypatch):
    """The mixed case, which is the normal one mid-session."""
    assert _dirty(monkeypatch, "?? results/a.json\n M src/claims/heuristic.py") is True


def test_a_clean_tree_is_clean(monkeypatch):
    assert _dirty(monkeypatch, "") is False


def test_no_git_is_unknown_rather_than_clean(monkeypatch):
    """Outside a repo the honest answer is `null`. Reporting `false` would claim
    reproducibility that nothing checked."""
    monkeypatch.setattr("common.provenance._git", lambda *a, **k: None)
    assert git_info()["dirty"] is None
