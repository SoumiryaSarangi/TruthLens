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

## IndicXlit: ruled out, and not only because fairseq will not build

The Day 2 spike ran in a throwaway venv and took 43 seconds to fail. Two
findings, and the second is the decisive one:

1. `ai4bharat-transliteration` 1.1.3 pulls `fairseq` 0.12.2, whose `libbleu` C
   extension needs MSVC build tools this machine does not have. Fixable.
2. Resolving it also pulls **`tensorflow` 2.21, `torch` 2.14 (the CPU build),
   `tensorflow-addons`, `tf2crf` and `urduhack`** -- roughly 5 GB, and the CPU
   torch would silently replace the CUDA build every other stage depends on.

So even with a compiler it does not belong in this environment. Installing a
transliterator must not cost the project its GPU. If IndicXlit is wanted later
it goes in its own venv behind a subprocess boundary, or through WSL.

Slotting a replacement in means adding one class here and one entry in
`TRANSLITERATORS`; nothing else changes.
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


class LexiconTransliterator(RuleBasedTransliterator):
    """Dakshina's lexicon first, the rules above for every word it lacks.

    Added after the test run (Phase 7), for the failure the rules cannot fix by
    construction -- word-MEDIAL long vowels. "Taj Mahal Shah Jahan ne banwaya
    tha" came out तज महल शह जहन, the search never reached the Taj Mahal
    article, and the verdict model's claim prior refuted a true claim at 0.72.

    Dakshina's TRAIN lexicon pairs native words with the romanizations people
    typed for them, with counts; read backwards, a typed word maps to its most
    attested native spelling (ties: alphabetical, so the output is fixed). The
    same file builds the synthetic romanized eval set (`romanize.py`), read the
    other way; neither direction is evaluated on Dakshina itself.
    """

    impl = "lexicon"

    def __init__(self, root: str | None = None) -> None:
        self._root = root

    def _lexicon(self, lang: str) -> dict[str, str]:
        from preprocess.romanize import DAKSHINA

        cache = self.__dict__.setdefault("_cache", {})
        if lang not in cache:
            cache[lang] = load_inverse_lexicon(lang, root=self._root or DAKSHINA)
        return cache[lang]

    def to_native(self, text: str, lang: str) -> str:
        target = LANG_SCRIPT.get(lang)
        if not target or not text:
            return text
        lexicon = self._lexicon(lang)
        rules = super().to_native

        def one(match: re.Match[str]) -> str:
            word = match.group()
            return lexicon.get(word.lower()) or rules(word, lang)

        return _WORD.sub(one, text)


def load_inverse_lexicon(lang: str, root) -> dict[str, str]:
    """typed romanization -> its most attested native word, Dakshina train only."""
    import csv
    from collections import defaultdict
    from pathlib import Path

    path = Path(root) / lang / f"{lang}.translit.sampled.train.tsv"
    if not path.is_file():
        return {}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(row) < 3 or not row[1].strip() or " " in row[1].strip():
                continue
            counts[row[1].strip().lower()][row[0]] += int(row[2] or 0)
    return {roman: min(natives.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            for roman, natives in counts.items()}


TRANSLITERATORS = {"rulebased": RuleBasedTransliterator, "lexicon": LexiconTransliterator}


def build_transliterator(impl: str = "rulebased"):
    if impl not in TRANSLITERATORS:
        raise ValueError(
            f"unknown transliterator {impl!r}; registered: {sorted(TRANSLITERATORS)}"
        )
    return TRANSLITERATORS[impl]()
