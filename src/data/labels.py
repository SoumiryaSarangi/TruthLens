"""The single registry of label sets.

Every label string in a split file, a predictions file or a config is validated
against this module. Defining them in one place is what stops "NEI" in one file
and "Not Enough Evidence" in another from quietly becoming two classes and
deflating macro-F1 by a class-worth of zeros.
"""

from __future__ import annotations

from typing import Final


class UnresolvedLabelMapping(LookupError):
    """Raised for a label whose mapping is a project decision, not a detail."""


# -- The project's output scheme (CLAUDE.md, "Metric definitions") -------------
VERDICT_4CLASS: Final[tuple[str, ...]] = ("Supported", "Refuted", "NEI", "NotAClaim")

# -- Source dataset schemes ----------------------------------------------------
AVERITEC_LABELS: Final[tuple[str, ...]] = (
    "Supported",
    "Refuted",
    "Not Enough Evidence",
    "Conflicting Evidence/Cherrypicking",
)

CHECKWORTHY_BINARY: Final[tuple[str, ...]] = ("Yes", "No")
STANCE_3CLASS: Final[tuple[str, ...]] = ("Supports", "Refutes", "Neutral")
SPAN_BIO: Final[tuple[str, ...]] = ("B-CLAIM", "I-CLAIM", "O")

LABEL_SETS: Final[dict[str, tuple[str, ...]]] = {
    "verdict_4class": VERDICT_4CLASS,
    "averitec": AVERITEC_LABELS,
    "checkworthy_binary": CHECKWORTHY_BINARY,
    "stance_3class": STANCE_3CLASS,
    "span_bio": SPAN_BIO,
}


# -----------------------------------------------------------------------------
# AVeriTeC -> TruthLens
# -----------------------------------------------------------------------------
# TODO(session-2): the two schemes do not line up and the gap is a modelling
# decision, not a scaffolding one. It is left to fail loudly rather than be
# guessed here.
#
#   AVeriTeC has 'Conflicting Evidence/Cherrypicking'; TruthLens has no such
#   class. TruthLens has 'NotAClaim', which AVeriTeC never produces because it
#   comes from the Phase 3 check-worthiness stage, upstream of the verdict.
#
# The three options, to be decided and recorded in docs/build-plan.md:
#   (a) map Conflicting -> NEI. Simple, defensible ("we cannot adjudicate"),
#       but it discards a distinction AVeriTeC paid annotators for and inflates
#       the NEI class.
#   (b) drop Conflicting rows from train/eval. Cleanest metric, but changes the
#       denominator, so published AVeriTeC numbers stop being comparable.
#   (c) keep 5 classes internally and collapse only for the report table.
#
# Whichever is chosen, write it here AND in the report; the class distribution
# it produces belongs in docs/data-profile.md.
_AVERITEC_TO_TRUTHLENS: Final[dict[str, str]] = {
    "Supported": "Supported",
    "Refuted": "Refuted",
    "Not Enough Evidence": "NEI",
    # "Conflicting Evidence/Cherrypicking": UNDECIDED -- see above.
}


def map_averitec_label(label: str) -> str:
    """Map an AVeriTeC gold label into the TruthLens 4-class scheme."""
    if label not in AVERITEC_LABELS:
        raise ValueError(f"{label!r} is not an AVeriTeC label; expected one of {AVERITEC_LABELS}")
    try:
        return _AVERITEC_TO_TRUTHLENS[label]
    except KeyError:
        raise UnresolvedLabelMapping(
            f"No agreed mapping for AVeriTeC label {label!r}. This is an open project "
            "decision, see the TODO(session-2) block in src/data/labels.py. Decide it "
            "and record it in docs/build-plan.md before evaluating on AVeriTeC."
        ) from None


def get_label_set(name: str) -> tuple[str, ...]:
    try:
        return LABEL_SETS[name]
    except KeyError:
        raise ValueError(
            f"Unknown label set {name!r}. Known: {sorted(LABEL_SETS)}. "
            "Add it to src/data/labels.py rather than inventing labels in a config."
        ) from None


def validate_labels(labels: object, label_set: str, *, where: str) -> None:
    """Fail on any label outside the declared set, naming the offender."""
    allowed = set(get_label_set(label_set))
    seen = set(labels) if not isinstance(labels, str) else {labels}
    unknown = sorted(seen - allowed)
    if unknown:
        raise ValueError(
            f"{where}: label(s) {unknown} are not in label set {label_set!r} "
            f"({sorted(allowed)}). A typo'd label silently becomes its own class."
        )
