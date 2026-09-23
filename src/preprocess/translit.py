"""Romanized Hindi/Punjabi -> native script (FR-5).

One interface, so which transliterator runs is a config choice:

    RuleBasedTransliterator   indic-transliteration 2.3.82, pinned and working
    (IndicXlit)               the learned upgrade -- see the note below

## Why the rule-based one is weak, stated up front

ITRANS and its relatives were designed to write Sanskrit **unambiguously** in
ASCII: `A` is long aa, `I` is long ii, every vowel is marked. Real people typing
Hindi in a WhatsApp message mark almost nothing. They write `sarkar`, not
`sarakAra`; `kaha`, not `kahA`.

Some of that is recoverable by rule and some is not, and the split is sharp:

  recoverable    A word-FINAL vowel. Hindi deletes the final schwa in speech
                 but writes it, so a word typed ending in a consonant needs the
                 inherent vowel restored (`sach` -> `sacha` -> सच), while a word
                 typed ending in `a` almost always means long aa
                 (`kaha` -> `kahA` -> कहा).

  NOT recoverable  A word-MEDIAL long vowel. `sarkar` is written identically
                 whether the second vowel is short or long, and choosing needs a
                 lexicon. `sarkar` comes out सरकर, not सरकार, and no rule fixes
                 it.

So this implementation is a floor, not a solution. It exists so the learned
model has something to be measured against, and its errors are reported rather
than smoothed over. `docs/results.md` carries the CER and WER.

## IndicXlit

`ai4bharat-transliteration` depends on fairseq, which does not install cleanly
on Windows + Python 3.11. The Day 2 spike could not run at all because `uv` is
no longer present on this machine, so the package was never resolved -- the
failure is a tooling one, not a verdict on IndicXlit. Recorded in
docs/project-log.md. Slotting it in means adding one class here and one
`register(...)` line; nothing else changes.
"""

from __future__ import annotations

import re

LANG_SCRIPT = {"hi": "DEVANAGARI", "pa": "GURMUKHI"}

_VOWELS = "aeiou"
_LONG = "AIU"

# Doubled vowels are the one long-vowel convention informal romanization does
# use consistently ("aa", "ee", "oo"), so they are worth mapping. The rest are
# spelling habits that ITRANS would otherwise read as separate consonants.
_DIGRAPHS = (
    ("aa", "A"), ("ii", "I"), ("ee", "I"), ("oo", "U"), ("uu", "U"),
    ("ck", "k"), ("kh", "kh"), ("gh", "gh"), ("ph", "f"),
)

_WORD = re.compile(r"[A-Za-z]+")


def _prepare(word: str) -> str:
    """Informal romanization -> something ITRANS can read."""
    out = word.lower()
    for a, b in _DIGRAPHS:
        out = out.replace(a, b)
    if not out:
        return out
    last = out[-1]
    previous = out[-2] if len(out) > 1 else ""
    # A final vowel only counts as long when a CONSONANT precedes it. After
    # another vowel it is the second half of a diphthong, and lengthening it
    # breaks the commonest word in the data: `hai` -> `haI` gives हई, not है.
    after_vowel = previous in _VOWELS + _LONG
    if last == "a" and not after_vowel:
        # Written final `a` is long aa far more often than it is the inherent
        # schwa, because the schwa is precisely the vowel people don't type.
        out = out[:-1] + "A"
    elif last in "iu" and not after_vowel:
        out = out[:-1] + ("I" if last == "i" else "U")
    elif last not in _VOWELS + _LONG:
        # Ends in a consonant: restore the inherent vowel, or ITRANS emits a
        # halant and the word ends in a dead consonant (सच् instead of सच).
        out = out + "a"
    return out


class RuleBasedTransliterator:
    """indic-transliteration, with informal-spelling pre-normalisation."""

    name = "translit"
    impl = "rulebased"

    def to_native(self, text: str, lang: str) -> str:
        """Latin -> Devanagari/Gurmukhi. Returns `text` unchanged for `en`."""
        target = LANG_SCRIPT.get(lang)
        if not target or not text:
            return text
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        scheme = getattr(sanscript, target)

        def one(match: re.Match[str]) -> str:
            return transliterate(_prepare(match.group()), sanscript.ITRANS, scheme)

        # Only letter runs are converted, so digits, emoji, URLs and the English
        # words that code-mixed forwards are full of pass through untouched.
        return _WORD.sub(one, text)

    def to_roman(self, text: str, lang: str) -> str:
        """Devanagari/Gurmukhi -> Latin.

        Used to build the synthetic romanized eval sets and the X-CLAIM
        round-trip, not in the serving path.
        """
        source = LANG_SCRIPT.get(lang)
        if not source or not text:
            return text
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        romanized = transliterate(text, getattr(sanscript, source), sanscript.ITRANS)
        # ITRANS output is case-significant (`A` = long aa). Lowercasing it is
        # what makes the result look like something a person would actually
        # type, which is the whole point of a synthetic romanized set.
        return romanized.lower()


TRANSLITERATORS = {"rulebased": RuleBasedTransliterator}


def build_transliterator(impl: str = "rulebased"):
    if impl not in TRANSLITERATORS:
        raise ValueError(
            f"unknown transliterator {impl!r}; registered: {sorted(TRANSLITERATORS)}"
        )
    return TRANSLITERATORS[impl]()
