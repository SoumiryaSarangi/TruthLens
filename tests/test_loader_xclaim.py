"""X-CLAIM's span index convention, pinned.

Every span number in this project rests on one undocumented assumption: that
`span_end_index` is **inclusive**. Nothing upstream says so. Getting it wrong
shifts every span by exactly one token, which is small enough that the metrics
stay plausible and large enough that they are all wrong.

It was established by counting, not by reading: across all of X-CLAIM,
`span_end_index == len(tokens)` occurs **0** times and `== len(tokens) - 1`
occurs **2,897** times. Exclusive indexing would produce the opposite.

Two layers here, on purpose:

- The pure tests run everywhere, including CI, and pin what the code DOES with
  the convention -- that `end` is included in the span and that a row claiming
  an exclusive end is rejected rather than quietly clipped.
- The corpus tests re-measure the evidence and skip where `data/raw/x_claim/`
  is absent, which is CI. They are the ones that would catch the source data
  changing under us.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from data import loaders

ROOT = Path(__file__).resolve().parents[1]

HAVE_SOURCE = loaders.sources_available("x_claim")
needs_source = pytest.mark.skipif(
    not HAVE_SOURCE, reason="data/raw/x_claim/ is not redistributable"
)


def _build_span_gold():
    """Load the builder by path; `scripts/` is not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "build_span_gold", ROOT / "scripts" / "build_span_gold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_row(tokens: list[str], start: int, end: int) -> dict[str, str]:
    """One X-CLAIM CSV row as the file stores it: Python literals in strings."""
    return {"tokens": repr(tokens), "span_start_index": repr([start]),
            "span_end_index": repr([end])}


def write_corpus(directory: Path, end: int, tokens=("a", "b", "c")) -> Path:
    """A one-row `train-en.csv` in X-CLAIM's own format, for the guard tests."""
    path = directory / "train-en.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["tokens", "span_start_index", "span_end_index"])
        writer.writeheader()
        writer.writerow(raw_row(list(tokens), 0, end))
    return path


# -----------------------------------------------------------------------------
# The convention, as the code applies it. No data files needed.
# -----------------------------------------------------------------------------


def test_the_end_index_is_inclusive():
    """The token AT `end` is part of the claim, not one past it."""
    tokens = ["Sarkar", "ne", "kaha", "6000", "rupaye", "milenge", "sabko"]
    parsed = loaders._parse_span_row(raw_row(tokens, 2, 5))
    assert parsed is not None
    got, start, end = parsed
    assert got == tokens
    assert (start, end) == (2, 5)
    assert got[start:end + 1] == ["kaha", "6000", "rupaye", "milenge"], (
        "slicing with end+1 must recover the claim. If this fails, every span "
        "in the project is off by one token."
    )


def test_a_span_ending_at_len_tokens_is_refused_not_clipped():
    """That row would only be valid under EXCLUSIVE indexing.

    Rejecting is the point. Clipping it to the last token would let a corpus
    that had switched conventions load cleanly and score slightly wrong
    forever, which is the failure this whole file exists to prevent.
    """
    tokens = ["a", "b", "c"]
    assert loaders._parse_span_row(raw_row(tokens, 0, len(tokens))) is None


def test_a_whole_post_span_ends_at_len_minus_one():
    tokens = ["a", "b", "c", "d"]
    parsed = loaders._parse_span_row(raw_row(tokens, 0, len(tokens) - 1))
    assert parsed is not None
    assert parsed[1:] == (0, 3)


@pytest.mark.parametrize("item", [
    {"tokens": "['a','b']", "span_start_index": "[0,1]", "span_end_index": "[0,1]"},
    {"tokens": "[]", "span_start_index": "[0]", "span_end_index": "[0]"},
    {"tokens": "not a literal", "span_start_index": "[0]", "span_end_index": "[0]"},
    {"tokens": "['a','b']", "span_start_index": "[1]", "span_end_index": "[0]"},
    {"tokens": "['a','b']", "span_start_index": "[-1]", "span_end_index": "[1]"},
])
def test_unusable_rows_are_skipped_rather_than_guessed(item):
    assert loaders._parse_span_row(item) is None


def test_bio_tags_include_the_end_token():
    """The gold builder's tagging, which is where the convention reaches the metrics."""
    to_bio = _build_span_gold().to_bio
    assert to_bio(6, 2, 4) == ["O", "O", "B-CLAIM", "I-CLAIM", "I-CLAIM", "O"]


def test_a_single_token_span_is_b_only():
    to_bio = _build_span_gold().to_bio
    assert to_bio(3, 1, 1) == ["O", "B-CLAIM", "O"]


def test_the_derived_negative_excludes_the_whole_claim():
    """`load_xclaim_checkworthy` slices with `end + 1`; an off-by-one would leak
    the claim's last token into the text labelled "not a claim"."""
    tokens = ["Good", "morning", "Sarkar", "ne", "kaha", "forward", "to", "all"]
    parsed = loaders._parse_span_row(raw_row(tokens, 2, 4))
    assert parsed is not None
    got, start, end = parsed
    assert got[:start] + got[end + 1:] == ["Good", "morning", "forward", "to", "all"]


def test_the_builder_refuses_when_the_convention_flips(tmp_path, monkeypatch):
    """The guard is armed, not merely present.

    Fabricates a corpus that uses EXCLUSIVE indexing and checks the builder
    stops. Needs no real data, so this one runs in CI too -- the guard is the
    thing most worth having everywhere.
    """
    module = _build_span_gold()
    write_corpus(tmp_path, end=3)          # end == len(tokens): EXCLUSIVE
    monkeypatch.setattr(module, "RAW", tmp_path)
    with pytest.raises(module.SpanConventionError):
        module.check_convention(langs=("en",), splits=("train",))


def test_the_builder_accepts_an_inclusive_corpus(tmp_path, monkeypatch):
    """The other half of the guard: it must not refuse correct data."""
    module = _build_span_gold()
    write_corpus(tmp_path, end=2)          # end == len(tokens) - 1: INCLUSIVE
    monkeypatch.setattr(module, "RAW", tmp_path)
    evidence = module.check_convention(langs=("en",), splits=("train",))
    assert evidence == {"rows": 1, "end_at_len": 0,
                        "end_at_len_minus_1": 1, "multi_span": 0}


# -----------------------------------------------------------------------------
# The evidence itself, re-measured. Skips in CI, where the corpus cannot exist.
# -----------------------------------------------------------------------------


@needs_source
def test_the_corpus_still_supports_inclusive_indexing():
    """Counts it again rather than trusting the number in the docstring."""
    module = _build_span_gold()
    evidence = module.check_convention()
    assert evidence["rows"] > 0
    assert evidence["end_at_len"] == 0, (
        "a row now ends at len(tokens), which is only possible under EXCLUSIVE "
        "indexing. Re-derive the convention before trusting any span number."
    )
    assert evidence["end_at_len_minus_1"] > 0, (
        "no row ends at len(tokens)-1, so there is no longer positive evidence "
        "for inclusive indexing either. Do not assume; measure."
    )


@needs_source
def test_every_raw_span_is_in_range_under_inclusive_indexing():
    """Re-measured on dev-en: `end` must always be a valid index, never len()."""
    module = _build_span_gold()
    rows = module.raw_rows("en", "dev")
    assert rows, "dev-en is empty"
    parsed = [loaders._parse_span_row(r) for r in rows]
    usable = [p for p in parsed if p is not None]
    assert len(usable) / len(rows) > 0.95, (
        f"only {len(usable)}/{len(rows)} dev-en rows parse. The gold builder "
        "silently skips the rest, so a drop here shrinks the eval set."
    )
    for tokens, start, end in usable:
        assert 0 <= start <= end < len(tokens)
