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
# Five classes. `Conflicting` is carried through from AVeriTeC rather than
# being collapsed into NEI: "the evidence disagrees with itself" and "there is
# no evidence" are different answers, and a system that tells a user which one
# it is is more useful than one that says "unsure" to both. `NotAClaim` comes
# from the Phase 3 check-worthiness stage, upstream of the verdict, so AVeriTeC
# never produces it and it will have zero support on AVeriTeC-only evaluations.
VERDICT_5CLASS: Final[tuple[str, ...]] = (
    "Supported", "Refuted", "Conflicting", "NEI", "NotAClaim",
)

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
    "verdict_5class": VERDICT_5CLASS,
    "averitec": AVERITEC_LABELS,
    "checkworthy_binary": CHECKWORTHY_BINARY,
    "stance_3class": STANCE_3CLASS,
    "span_bio": SPAN_BIO,
}


# -----------------------------------------------------------------------------
# AVeriTeC -> TruthLens
# -----------------------------------------------------------------------------
# RESOLVED: the verdict scheme was widened to five classes so that AVeriTeC's
# fourth label survives the mapping intact.
#
# The rejected alternative was collapsing Conflicting into NEI. That would have
# thrown away a distinction AVeriTeC paid annotators to make, inflated NEI, and
# made the per-class F1 for NEI mean two different things at once.
#
# Consequences to keep in mind when reading results:
#   * `NotAClaim` has ZERO support on AVeriTeC-only evaluations, because
#     AVeriTeC claims are all already claims. Macro-F1 averages over every
#     declared class, so an AVeriTeC-only run carries a structural 0 for that
#     class and its macro-F1 is bounded above by 4/5 = 0.80. This is intended:
#     the alternative -- averaging only over classes that appear -- would make
#     the number jump when a class happens to show up.
#   * `Conflicting` is rare in AVeriTeC. Expect a small, noisy per-class F1 and
#     read it with its support column, not on its own.
_AVERITEC_TO_TRUTHLENS: Final[dict[str, str]] = {
    "Supported": "Supported",
    "Refuted": "Refuted",
    "Not Enough Evidence": "NEI",
    "Conflicting Evidence/Cherrypicking": "Conflicting",
}


def map_averitec_label(label: str) -> str:
    """Map an AVeriTeC gold label into the TruthLens 5-class scheme."""
    if label not in AVERITEC_LABELS:
        raise ValueError(f"{label!r} is not an AVeriTeC label; expected one of {AVERITEC_LABELS}")
    try:
        return _AVERITEC_TO_TRUTHLENS[label]
    except KeyError:  # pragma: no cover - every AVeriTeC label is now mapped
        raise UnresolvedLabelMapping(
            f"AVeriTeC label {label!r} has no mapping in _AVERITEC_TO_TRUTHLENS. "
            "The upstream label set must have changed; decide the mapping "
            "deliberately rather than defaulting it."
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
