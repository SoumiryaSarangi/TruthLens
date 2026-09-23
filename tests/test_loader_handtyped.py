"""The hand-typed forwards loader (FR-26).

The source CSV is people's own writing and is gitignored, so these skip in CI
the same way MultiClaim's would. The mapping table is tested regardless, because
it is a set of hand-made decisions and is the part most likely to be edited
carelessly later.
"""

from __future__ import annotations

import pytest

from data import loaders
from data.labels import CHECKWORTHY_BINARY
from data.splits import LANGS, validate_split_record

HAVE_SOURCE = loaders.sources_available("handtyped")
needs_source = pytest.mark.skipif(
    not HAVE_SOURCE, reason="data/raw/handtyped/forwards.csv is not redistributable"
)


def test_every_mixed_assignment_is_a_real_language():
    """`mixed` is not a language value; each row must land on one that is."""
    for row_id, (lang, reason) in loaders.MIXED_LANG.items():
        assert lang in LANGS, f"{row_id} assigned {lang!r}"
        assert reason, f"{row_id} has no stated reason"


def test_the_uncertain_assignment_is_declared():
    """A close call recorded as a close call, not smoothed into the table."""
    assert set(loaders.MIXED_UNCERTAIN) <= set(loaders.MIXED_LANG)


@needs_source
def test_loads_one_hundred_rows_into_dev_only():
    by_split = loaders.handtyped_rows()
    assert set(by_split) == {"dev"}, "an eval-only set must not create a train split"
    assert len(by_split["dev"]) == 100


@needs_source
def test_records_are_valid_split_rows():
    for row in loaders.handtyped_rows()["dev"]:
        validate_split_record(row.record, where="handtyped")


@needs_source
def test_uid_encodes_the_collector_id_so_it_survives_edits():
    """uid indexes off `hw042`, not a running counter.

    If it were positional, deleting one row would renumber every row after it
    and silently repoint every result built against the old split.
    """
    rows = {r.record["source_id"]: r.record["uid"] for r in loaders.handtyped_rows()["dev"]}
    assert rows["handtyped:hw001"].endswith(":00001")
    assert rows["handtyped:hw100"].endswith(":00100")


@needs_source
def test_label_is_check_worthiness_not_a_verdict():
    """These forwards have no verified answer; inventing one would be worse."""
    rows = loaders.handtyped_rows()["dev"]
    assert {r.record["label_set"] for r in rows} == {"checkworthy_binary"}
    assert {r.record["label"] for r in rows} <= set(CHECKWORTHY_BINARY)
    assert sum(1 for r in rows if r.record["label"] == "No") == 15


@needs_source
def test_mixed_rows_keep_their_declaration_in_notes():
    rows = {r.record["source_id"]: r.record for r in loaders.handtyped_rows()["dev"]}
    for row_id in loaders.MIXED_LANG:
        record = rows[f"handtyped:{row_id}"]
        assert "declared mixed" in record["notes"]


@needs_source
def test_every_row_is_latin_script():
    """The whole point of the set. A native-script row here is a collection bug."""
    rows = loaders.handtyped_rows()["dev"]
    assert {r.record["script"] for r in rows} == {"latn"}
