"""Per-row script detection.

Never infer script from the language label. X-CLAIM's `train-pa.csv` contains
249 Gurmukhi rows, 57 Devanagari rows and 39 Latin rows; `train-hi.csv`
contains 56 Latin rows. Assuming "pa means Gurmukhi" would silently put
romanized and Devanagari posts into the native-script column and destroy the
one comparison this project exists to make.

No model here, just Unicode ranges. Language identification (fastText) is a
different problem and arrives in Phase 2; this answers only "what alphabet is
this written in", which is the axis the report splits on.
"""

from __future__ import annotations

import unicodedata

# Unicode blocks. Latin is counted from the ASCII letter range plus Latin-1
# supplement letters, which is enough to separate romanized Indic text from
# native script.
_DEVANAGARI = ((0x0900, 0x097F), (0xA8E0, 0xA8FF))   # + Devanagari Extended
_GURMUKHI = ((0x0A00, 0x0A7F),)
_LATIN = ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F))

SCRIPTS: tuple[str, ...] = ("deva", "guru", "latn")

# Below this many script-bearing characters, a verdict is not meaningful --
# the row is mostly digits, punctuation or emoji.
MIN_SCRIPT_CHARS = 3


def _in(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= codepoint <= hi for lo, hi in ranges)


def script_counts(text: str) -> dict[str, int]:
    """Count script-bearing characters by script."""
    counts = dict.fromkeys(SCRIPTS, 0)
    for char in unicodedata.normalize("NFC", text or ""):
        cp = ord(char)
        if _in(cp, _DEVANAGARI):
            counts["deva"] += 1
        elif _in(cp, _GURMUKHI):
            counts["guru"] += 1
        elif _in(cp, _LATIN):
            counts["latn"] += 1
    return counts


def detect_script(text: str, *, default: str = "latn") -> str:
    """The dominant script. Falls back to `default` for text with too few
    script-bearing characters to judge (pure numerals, emoji, punctuation).
    """
    counts = script_counts(text)
    total = sum(counts.values())
    if total < MIN_SCRIPT_CHARS:
        return default
    return max(SCRIPTS, key=lambda s: (counts[s], -SCRIPTS.index(s)))


def is_romanized(text: str, lang: str) -> bool:
    """True when an Indic-language row is written in Latin script.

    This is the romanized-vs-native axis. English is never 'romanized' -- it
    is natively Latin -- so it always returns False.
    """
    if lang == "en":
        return False
    return detect_script(text) == "latn"


def script_purity(text: str) -> float:
    """Share of script-bearing characters belonging to the dominant script.

    1.0 is a single-script row; values near 0.5 indicate code-mixing, which is
    the normal case for WhatsApp forwards and worth reporting rather than
    hiding behind a single label.
    """
    counts = script_counts(text)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return max(counts.values()) / total
