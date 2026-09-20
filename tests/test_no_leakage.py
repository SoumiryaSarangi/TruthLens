"""Asserts zero claim overlap between train, dev and test in the real splits.

    make leakage      # run after ANY data change

This is the Phase 0 checklist item from docs/build-plan.md. It is parametrized
over whatever exists under data/splits/, so it grows automatically as datasets
are added in Session 2.

With no splits built yet it SKIPS with a stated reason -- it does not pass
quietly, because a silent pass on an empty directory is indistinguishable from
a real one. Whether the detector can fail at all is established separately, in
tests/test_leakage_detector.py, against fixtures with planted leaks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from data.leakage import failures, find_leakage, format_report
from data.splits import discover_splits, load_split

SPLITS_ROOT = Path("data/splits")
REPORTS = Path("reports")

DATASETS = sorted(discover_splits(SPLITS_ROOT))

pytestmark = pytest.mark.leakage


def _load(dataset: str) -> dict[str, list[dict]]:
    return {
        name: load_split(path)
        for name, path in discover_splits(SPLITS_ROOT)[dataset].items()
    }


@pytest.mark.skipif(bool(DATASETS), reason="splits exist; the real checks below run")
def test_no_splits_built_yet():
    """Placeholder so the suite reports honestly before Session 2 builds splits."""
    pytest.skip(
        f"No datasets under {SPLITS_ROOT}. Frozen splits are built in Session 2 "
        "(docs/build-plan.md, 'Phase 0, step 2'). The leakage detector itself is "
        "exercised against planted leaks in tests/test_leakage_detector.py."
    )


@pytest.mark.parametrize("dataset", DATASETS)
def test_no_leakage_between_splits(dataset: str):
    splits = _load(dataset)
    if len(splits) < 2:
        pytest.skip(f"{dataset} has only one split ({list(splits)}); nothing to compare")

    found = find_leakage(dataset, splits)
    fails = failures(found)

    if found:
        REPORTS.mkdir(exist_ok=True)
        report_path = REPORTS / f"leakage-{dataset}.md"
        report_path.write_text(format_report(dataset, found), encoding="utf-8")
    else:
        report_path = None

    assert not fails, (
        f"\n{len(fails)} leak(s) between splits of {dataset!r}.\n"
        + "\n".join(f"  {f.kind}: {f.uid_a} <-> {f.uid_b} ({f.detail})" for f in fails[:20])
        + (f"\n  ... and {len(fails) - 20} more" if len(fails) > 20 else "")
        + (f"\nFull report: {report_path}" if report_path else "")
        + "\n\nDo NOT fix this by regenerating data/splits/. Work out where the "
          "duplicate came from upstream, then decide deliberately and record it "
          "in docs/split-changelog.md."
    )


@pytest.mark.parametrize("dataset", DATASETS)
def test_uids_are_unique_within_each_split(dataset: str):
    """load_split raises on a duplicate uid; this pins that as a requirement."""
    splits = _load(dataset)
    for name, rows in splits.items():
        uids = [r["uid"] for r in rows]
        assert len(uids) == len(set(uids)), f"{dataset}/{name} has duplicate uids"


@pytest.mark.parametrize("dataset", DATASETS)
def test_every_row_declares_language_and_script(dataset: str):
    """Per-language and per-script reporting is mandatory, so the fields must be present."""
    for name, rows in _load(dataset).items():
        for rec in rows:
            assert rec.get("lang"), f"{dataset}/{name}: {rec.get('uid')} has no lang"
            assert rec.get("script"), f"{dataset}/{name}: {rec.get('uid')} has no script"
