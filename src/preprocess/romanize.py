"""Native script -> informal Latin, the way people type Hindi and Punjabi (FR-26).

The opposite direction from `transliterate.py`. It exists to BUILD an eval set,
not to serve: X-CLAIM's Hindi and Punjabi spans have no romanized version, so
the romanization penalty for span identification could not be measured at all.
`x_claim_romanized` is X-CLAIM dev/test romanized by this module.

Two layers, word by word:

1. **Dakshina's train lexicon** -- native words with the romanizations real
   annotators typed, and how many typed each. The most-attested one wins
   (ties: shorter, then alphabetical, so the output is deterministic).
2. **Rules** for every word the lexicon lacks: a consonant-vowel table with
   word-final and VC_CV schwa deletion, informal vowel spellings ("karna", not
   "karanaa"), Gurmukhi addak doubling, nasals as "n".

Word by word, and never across a space: every whitespace token maps to exactly
one non-empty token, so X-CLAIM's token-indexed span gold carries over 1:1.

Synthetic romanization is cleaner than real typing -- one spelling per word,
no code-mixing, no abbreviations -- so a penalty measured on it is a LOWER
bound. Its distance from real typing is measured against the hand-typed
Punjabi pairs (configs/p7_romanize_handtyped.yaml), not assumed.
"""

from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path

DAKSHINA = Path("data/raw/dakshina/extracted")

# Which lexicon reads which script. By SCRIPT, not by language: X-CLAIM's
# Punjabi files carry Devanagari rows too, and those are read as Hindi letters.
LEXICON_LANG = {"deva": "hi", "guru": "pa"}

# --- Devanagari ---------------------------------------------------------------
DEVA_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    # precomposed nukta forms
    "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f", "य़": "y",
}
DEVA_NUKTA = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f"}
DEVA_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e",
}
DEVA_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}

# --- Gurmukhi -----------------------------------------------------------------
GURU_CONSONANTS = {
    "ਕ": "k", "ਖ": "kh", "ਗ": "g", "ਘ": "gh", "ਙ": "n",
    "ਚ": "ch", "ਛ": "chh", "ਜ": "j", "ਝ": "jh", "ਞ": "n",
    "ਟ": "t", "ਠ": "th", "ਡ": "d", "ਢ": "dh", "ਣ": "n",
    "ਤ": "t", "ਥ": "th", "ਦ": "d", "ਧ": "dh", "ਨ": "n",
    "ਪ": "p", "ਫ": "ph", "ਬ": "b", "ਭ": "bh", "ਮ": "m",
    "ਯ": "y", "ਰ": "r", "ਲ": "l", "ਵ": "v", "ੜ": "r",
    "ਸ": "s", "ਹ": "h",
    "ਸ਼": "sh", "ਖ਼": "kh", "ਗ਼": "g", "ਜ਼": "z", "ਫ਼": "f", "ਲ਼": "l",
}
GURU_NUKTA = {"ਸ": "sh", "ਖ": "kh", "ਗ": "g", "ਜ": "z", "ਫ": "f", "ਲ": "l"}
GURU_VOWELS = {
    "ਅ": "a", "ਆ": "aa", "ਇ": "i", "ਈ": "ee", "ਉ": "u", "ਊ": "oo",
    "ਏ": "e", "ਐ": "ai", "ਓ": "o", "ਔ": "au", "ੲ": "i", "ੳ": "u",
}
GURU_MATRAS = {
    "ਾ": "aa", "ਿ": "i", "ੀ": "ee", "ੁ": "u", "ੂ": "oo",
    "ੇ": "e", "ੈ": "ai", "ੋ": "o", "ੌ": "au",
}

VIRAMA = {"्", "੍"}
NUKTA = {"़", "਼"}
NASALS = {"ं", "ँ", "ੰ", "ਂ"}
VISARGA = {chr(0x0903): "h", chr(0x0A03): "h"}      # Devanagari, Gurmukhi visarga
ADDAK = "ੱ"
DIGITS = {**{chr(0x0966 + i): str(i) for i in range(10)},
          **{chr(0x0A66 + i): str(i) for i in range(10)}}
DANDAS = {"।": ".", "॥": "."}

CONSONANTS = {**DEVA_CONSONANTS, **GURU_CONSONANTS}
NUKTA_FORMS = {**DEVA_NUKTA, **GURU_NUKTA}
VOWELS = {**DEVA_VOWELS, **GURU_VOWELS}
MATRAS = {**DEVA_MATRAS, **GURU_MATRAS}

# Informal typing shortens long vowels where nobody would double them.
FINAL_VOWEL = {"aa": "a", "ee": "i", "oo": "u"}


def _syllables(word: str) -> list[list[str]]:
    """[onset, vowel, coda] units. vowel is '' for a bare consonant, 'a*' for
    the inherent schwa (deletable), anything else explicit."""
    units: list[list[str]] = []
    i, n = 0, len(word)
    double_next = False
    while i < n:
        ch = word[i]
        if ch in CONSONANTS:
            onset = CONSONANTS[ch]
            i += 1
            if i < n and word[i] in NUKTA:
                onset = NUKTA_FORMS.get(ch, onset)
                i += 1
            if double_next:
                onset = onset[0] + onset
                double_next = False
            if i < n and word[i] in VIRAMA:
                units.append([onset, "", ""])
                i += 1
                continue
            if i < n and word[i] in MATRAS:
                units.append([onset, MATRAS[word[i]], ""])
                i += 1
            else:
                units.append([onset, "a*", ""])
        elif ch in VOWELS:
            units.append(["", VOWELS[ch], ""])
            i += 1
        elif ch in MATRAS:                       # a stray matra: keep its sound
            units.append(["", MATRAS[ch], ""])
            i += 1
        elif ch in NASALS:
            if units:
                units[-1][2] += "n"
            else:
                units.append(["", "", "n"])
            i += 1
        elif ch in VISARGA:
            if units:
                units[-1][2] += VISARGA[ch]
            i += 1
        elif ch == ADDAK:
            double_next = True
            i += 1
        elif ch in VIRAMA or ch in NUKTA:
            i += 1
        else:
            units.append([DIGITS.get(ch) or DANDAS.get(ch) or ch, "", ""])
            i += 1
    return units


def _has_vowel(unit: list[str]) -> bool:
    return unit[1] not in ("", "-")


def rule_romanize(word: str) -> str:
    """One word by rule. Deterministic, dependency-free, never empty for a
    non-empty word."""
    units = _syllables(word)
    if not units:
        return word
    # Word-final schwa: "ram" not "rama", for Hindi and Punjabi alike -- except
    # after a conjunct, where it is spoken and typed: "narendra", "mantra".
    if units[-1][1] == "a*" and len(units) > 1 and units[-2][1] != "":
        units[-1][1] = "-"
    # Medial schwa, the VC_CV rule (Ohala): "karna" not "karana". Right to left,
    # so a deletion is visible to the syllable before it.
    for i in range(len(units) - 2, 0, -1):
        if (units[i][1] == "a*" and not units[i][2] and _has_vowel(units[i - 1])
                and units[i + 1][0] and _has_vowel(units[i + 1])):
            units[i][1] = "-"
    out = []
    for k, (onset, vowel, coda) in enumerate(units):
        v = {"a*": "a", "-": ""}.get(vowel, vowel)
        if k == len(units) - 1 and not coda:
            v = FINAL_VOWEL.get(v, v)
        out.append(onset + v + coda)
    text = "".join(out)
    return text or word


@lru_cache(maxsize=4)
def load_lexicon(lang: str, root: Path = DAKSHINA) -> dict[str, str]:
    """native word -> its most-attested romanization, from Dakshina train only."""
    path = Path(root) / lang / f"{lang}.translit.sampled.train.tsv"
    if not path.is_file():
        return {}
    best: dict[str, tuple[int, int, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(row) < 3:
                continue
            native, roman, count = row[0], row[1].strip().lower(), int(row[2] or 0)
            if not roman or " " in roman:
                continue
            key = (-count, len(roman), roman)
            if native not in best or key < best[native]:
                best[native] = key
    return {native: key[2] for native, key in best.items()}


def _script_of(word: str) -> str | None:
    for ch in word:
        if "ऀ" <= ch <= "ॿ":
            return "deva"
        if "਀" <= ch <= "੿":
            return "guru"
    return None


def _split_punct(token: str) -> tuple[str, str, str]:
    """Leading punctuation, the word, trailing punctuation."""
    def is_punct(ch: str) -> bool:
        return ch in DANDAS or unicodedata.category(ch)[0] in "PS"
    start, end = 0, len(token)
    while start < end and is_punct(token[start]):
        start += 1
    while end > start and is_punct(token[end - 1]):
        end -= 1
    return token[:start], token[start:end], token[end:]


def romanize_token(token: str, lexicons: dict[str, dict[str, str]] | None = None) -> str:
    """One whitespace token -> one non-empty Latin token."""
    lead, core, trail = _split_punct(token)
    script = _script_of(core)
    if script is None:
        return "".join(DANDAS.get(c, DIGITS.get(c, c)) for c in token)
    lex = (lexicons if lexicons is not None else {}).get(script)
    if lex is None and lexicons is None:
        lex = load_lexicon(LEXICON_LANG[script])
    roman = (lex or {}).get(core) or rule_romanize(core)
    lead = "".join(DANDAS.get(c, c) for c in lead)
    trail = "".join(DANDAS.get(c, c) for c in trail)
    out = lead + roman + trail
    return out if out.strip() else token


def romanize_tokens(tokens: list[str],
                    lexicons: dict[str, dict[str, str]] | None = None) -> list[str]:
    out = [romanize_token(t, lexicons) for t in tokens]
    assert len(out) == len(tokens) and all(t and " " not in t for t in out)
    return out


def romanize(text: str, lexicons: dict[str, dict[str, str]] | None = None) -> str:
    """Whitespace-token by token, so token indices are preserved."""
    return " ".join(romanize_tokens(text.split(), lexicons))
