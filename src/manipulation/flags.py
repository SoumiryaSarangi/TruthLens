"""FR-19: flag persuasion techniques in a forward. Never changes the verdict.

Cut-list item 1's fallback, built as decided: no trained classifier, rules plus
zero-shot NLI. Labels are SemEval-2023 Task 3 subtask 3 technique NAMES -- a
subset that shows up in WhatsApp forwards and that a rule or one NLI hypothesis
can see:

    rules   Appeal_to_Time       "urgent", "turant", "ਜਲਦੀ", "before it is deleted"
            Appeal_to_Authority  "doctors say", "WHO", "NASA", "वैज्ञानिक"
            Appeal_to_Popularity "everyone knows", "sab log", "ਸਾਰੇ ਲੋਕ"
            Loaded_Language      "!!", ALL-CAPS runs, alarm emoji, "khatarnak"
            Repetition           a three-word phrase said three times
    NLI     Appeal_to_Fear-Prejudice, Exaggeration-Minimisation

**Unmeasured.** SemEval-2023 Task 3 needs registration and was never obtained,
so there is no gold to score these against; FR-19 is verified by demo (SRS
§3.5). The design therefore buys precision with recall: high NLI threshold, at
most three flags, keyword lists in each script a forward arrives in.

**Never changes the verdict.** The orchestrator runs this on the forward after
every verdict is decided and only copies the list onto each result.
"""

from __future__ import annotations

import re
from collections import Counter

MAX_FLAGS = 3

# Every list is matched lowercased against the forward AND its transliteration,
# so romanized Hindi meets the Devanagari list too.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "Appeal_to_Time": (
        "urgent", "immediately", "right now", "hurry", "asap", "last date",
        "today only", "before it is deleted", "before it's deleted", "before it gets deleted",
        "turant", "jaldi", "jaldi se", "abhi ke abhi", "aaj hi", "hune", "ajj hi",
        "तुरंत", "जल्दी", "आज ही", "अभी के अभी", "डिलीट होने से पहले",
        "ਤੁਰੰਤ", "ਜਲਦੀ", "ਹੁਣੇ", "ਅੱਜ ਹੀ",
    ),
    "Appeal_to_Authority": (
        "doctors say", "doctors have", "scientists say", "research shows", "study shows",
        "experts say", "nasa", "unesco", "aiims", "harvard",
        "doctor ne", "doctors ne", "vaigyanik", "scientist ne",
        "डॉक्टरों", "डॉक्टर ने", "वैज्ञानिक", "विशेषज्ञ",
        "ਡਾਕਟਰਾਂ", "ਡਾਕਟਰ ਨੇ", "ਵਿਗਿਆਨੀ", "ਮਾਹਿਰ",
    ),
    "Appeal_to_Popularity": (
        "everyone knows", "everybody knows", "everyone is", "millions of people",
        "sab log", "sabhi log", "saare log", "sare log", "sab jaante", "sab jante",
        "सब लोग", "सभी लोग", "सब जानते",
        "ਸਾਰੇ ਲੋਕ", "ਸਭ ਲੋਕ", "ਸਾਰੇ ਜਾਣਦੇ",
    ),
    "Loaded_Language": (
        "shocking", "dangerous", "deadly", "breaking", "beware", "alert",
        "khatarnak", "khatarnaak", "savdhan", "saavdhan", "sawdhan",
        "खतरनाक", "सावधान", "चौंकाने",
        "ਖ਼ਤਰਨਾਕ", "ਖਤਰਨਾਕ", "ਸਾਵਧਾਨ",
    ),
}
# Case-SENSITIVE: "WHO" the organisation, never "who" the pronoun.
AUTHORITY_ACRONYMS = ("WHO", "ICMR")

ALARM = re.compile("[\U0001F6A8⚠‼❗\U0001F534\U0001F631]")
SHOUTING = re.compile(r"\b[A-Z]{4,}\b")
EXCLAIM = re.compile(r"!{2,}|‼")

# Zero-shot NLI: hypothesis, and the P(entailment) above which it flags.
# The threshold is high on purpose and is not tuned on anything -- there is
# nothing to tune it on.
NLI_HYPOTHESES: dict[str, tuple[str, float]] = {
    "Appeal_to_Fear-Prejudice": ("This message tries to frighten the reader.", 0.90),
    "Exaggeration-Minimisation": ("This message makes an exaggerated claim.", 0.90),
}

ORDER = ("Appeal_to_Fear-Prejudice", "Appeal_to_Time", "Loaded_Language",
         "Exaggeration-Minimisation", "Appeal_to_Authority", "Appeal_to_Popularity",
         "Repetition")


def _contains(haystack: str, needle: str) -> bool:
    if needle.isascii():
        return re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", haystack) is not None
    return needle in haystack


def rule_flags(text: str, transliterated: str | None = None) -> set[str]:
    """Techniques visible to keywords and surface patterns alone."""
    raw = " ".join(t for t in (text, transliterated) if t)
    low = raw.lower()
    found = {label for label, words in KEYWORDS.items()
             if any(_contains(low, w) for w in words)}
    if any(acronym in raw for acronym in AUTHORITY_ACRONYMS):
        found.add("Appeal_to_Authority")
    if ALARM.search(raw) or EXCLAIM.search(raw) or len(SHOUTING.findall(text)) >= 2:
        found.add("Loaded_Language")
    words = re.findall(r"\w+", text.lower())
    trigrams = Counter(zip(words, words[1:], words[2:], strict=False))
    if trigrams and max(trigrams.values()) >= 3:
        found.add("Repetition")
    return found


class NoFlags:
    """`manipulation: none` -- the default; every evaluation config runs this."""

    impl = "none"

    def flags(self, text: str, transliterated: str | None = None) -> list[str]:
        return []


class RulesNLIFlags:
    """`manipulation: rules_nli` -- the served FR-19 fallback."""

    impl = "rules_nli"

    def __init__(self, nli=None, use_nli: bool = True):
        self._nli = nli
        self.use_nli = use_nli

    def _nli_flags(self, text: str) -> set[str]:
        if not self.use_nli:
            return set()
        if self._nli is None:
            from stance.nli import NLIStance

            self._nli = NLIStance()      # the resident model; NLIStance shares it
        labels = list(NLI_HYPOTHESES)
        results = self._nli.score_pairs([(text, NLI_HYPOTHESES[k][0]) for k in labels])
        return {label for label, res in zip(labels, results, strict=True)
                if res.probs.get("Supports", 0.0) >= NLI_HYPOTHESES[label][1]}

    def flags(self, text: str, transliterated: str | None = None) -> list[str]:
        if not text or not text.strip():
            return []
        found = rule_flags(text, transliterated) | self._nli_flags(text)
        return [label for label in ORDER if label in found][:MAX_FLAGS]
