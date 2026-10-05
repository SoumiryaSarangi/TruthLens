"""Cues that make an unverified message worth a warning ("Be careful with this one").

docs/careful-rule-protocol.md fixes this rule BEFORE it was measured. It replaces the earlier trigger, the
offline model's quiet lean toward "Refuted", which fired on almost every claim (122 of 125 true test claims) and
so told the reader nothing about THIS message. These cues are about the message: the shape of a typical hoax
(a miracle cure, a thing "they" hide, a charge or a ban or a giveaway announced from tomorrow) or a pressure
technique the rules in `manipulation.flags` already detect.

It never changes a verdict and is only a reason to word an unverified card as a warning. Lists are matched
lowercased against the text and its transliteration, like `manipulation.flags`.
"""
from __future__ import annotations

import re

from manipulation.flags import rule_flags

CURE_WORDS = (
    "cure", "cures", "cured", "curing", "kill", "kills", "killing", "prevent", "prevents", "heal", "heals",
    "theek ho", "theek kar", "theek hota", "theek ho jata", "ilaaj", "ilaj", "khatam", "khatm",
    "ठीक", "इलाज", "खत्म", "ਠੀਕ", "ਇਲਾਜ", "ਖਤਮ", "ਖ਼ਤਮ",
)
HEALTH_WORDS = (
    "cancer", "covid", "corona", "coronavirus", "virus", "diabetes", "sugar", "tumor", "tumour", "hiv", "aids",
    "asthma", "cough", "fever", "malaria", "dengue", "jaundice", "blood pressure", "kidney", "disease",
    "कैंसर", "कोरोना", "शुगर", "मधुमेह", "बीमारी", "ਕੈਂਸਰ", "ਕੋਰੋਨਾ", "ਸ਼ੂਗਰ", "ਬਿਮਾਰੀ",
)
CONCEAL_WORDS = (
    "don't reveal", "do not reveal", "don't want you to know", "do not want you to know", "hiding this",
    "hide this", "hidden from", "cover up", "covering up", "don't tell you", "not telling you", "big pharma",
    "chhupate", "chhupa", "chupate", "chupa rahe", "छुपा", "छिपा", "ਲੁਕਾ", "ਛੁਪਾ",
)
FREE_WORDS = ("free", "muft", "मुफ़्त", "मुफ्त", "ਮੁਫ਼ਤ", "ਮੁਫਤ")
GIVEAWAY_WORDS = (
    "laptop", "phone", "recharge", "ration", "tractor", "cylinder", "rupees", "gift", "data", "internet",
    "scholarship", "money", "₹", "रुपये", "ਰੁਪਏ",
)
DEADLINE_WORDS = (
    "from tomorrow", "from next month", "from midnight", "kal se", "agle mahine se", "कल से", "अगले महीने से",
    "ਕੱਲ੍ਹ ਤੋਂ", "ਕੱਲ ਤੋਂ",
)
THREAT_PHRASES = (
    "will start charging", "will be charged", "will charge you", "paise lagenge", "charge lagega", "paisa lagega",
    "will be blocked", "will be banned", "will be cancelled", "will be canceled", "will be closed",
    "will be deleted", "will be stopped", "will be shut", "band ho jayega", "band ho jaayega", "band ho jaega",
    "बंद हो जाएगा", "बंद हो जायेगा", "ਬੰਦ ਹੋ ਜਾਵੇਗਾ",
)


def _has(low: str, words: tuple[str, ...]) -> bool:
    for w in words:
        if w.isascii() and w.replace(" ", "").replace("'", "").isalpha():
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
                return True
        elif w in low:
            return True
    return False


def hoax_cues(text: str, transliterated: str | None = None) -> list[str]:
    """The hoax-shape cues in a message, by name (empty: none)."""
    low = " ".join(t for t in (text, transliterated) if t).lower()
    out = []
    if _has(low, CURE_WORDS) and _has(low, HEALTH_WORDS):
        out.append("miracle_cure")
    if _has(low, CONCEAL_WORDS):
        out.append("concealment")
    if _has(low, FREE_WORDS) and _has(low, GIVEAWAY_WORDS):
        out.append("giveaway")
    if _has(low, THREAT_PHRASES) or (_has(low, DEADLINE_WORDS) and _has(low, ("charge", "paise", "block", "ban", "band", "close"))):
        out.append("threat_or_charge")
    return out


def caution_cues(text: str, transliterated: str | None = None) -> list[str]:
    """Hoax-shape cues plus the pressure techniques `manipulation.flags` detects by rule. Sorted, deduplicated."""
    return sorted({*hoax_cues(text, transliterated), *(f"technique:{f}" for f in rule_flags(text, transliterated))})
