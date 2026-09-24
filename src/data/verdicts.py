"""Publisher ratings -> the 5-class verdict scheme (FR-8).

`FactCheckMatch.verdict` is annotated in `SYSTEM_DESIGN.md` §4 as "mapped from
the publisher's rating", and until Phase 4 nothing did the mapping. The fast
path cannot answer at all without it.

## What the data looks like, measured rather than assumed

MultiClaim's `ratings` column is populated for **all 78,077** fact-checks in the
indexed pool (0 missing) and holds a Python list of free-text publisher labels
in 39 languages. Corpus-wide there are 43,838 distinct strings, which sounds
hopeless and is not: the head is very steep. Over the indexed pool, `false`
alone is 28.3% and the top 70 strings cover 78.6%. Over the 3,943 fact-checks
the dev queries actually point at, `false` is 55.0% and the top 30 cover 82.2%.

## Exact matching only. No substring families.

Tempting and wrong. `half true` contains `true`, `mostly false` contains
`false`, `partiellement faux` contains `faux`, and `salah [misleading content]`
starts with `salah`. Every one of those would be mapped to the opposite or the
wrong class by a rule that looked plausible while reading it. An unmapped rating
costs a fall-through to the evidence path, which is the outcome we would have
had anyway; a MIS-mapped one puts a confident wrong verdict in front of a user.

## Judgement calls, stated because they move numbers

* **`misleading` and `missing context` map to `Conflicting`, not `Refuted`.**
  Our `Conflicting` is AVeriTeC's "Conflicting Evidence/Cherrypicking", and a
  misleading claim is one where the literal statement has some support while the
  full picture does not -- which is what cherrypicking means. Folding them into
  `Refuted` would be defensible on product grounds ("do not trust this") and
  would inflate an already dominant class. Recorded here so the alternative is
  visible rather than buried.
* **`satire` is deliberately unmapped.** Whether the claim is false or simply
  was never asserted seriously is genuinely ambiguous, and `NotAClaim` has a
  documented provenance -- it comes from check-worthiness upstream (`CLAUDE.md`),
  not from a publisher's label.
* **Disagreeing ratings decline.** A fact-check carrying two ratings that map to
  different verdicts is not evidence for either one.

The verdict distribution this produces is heavily `Refuted`, because fact-checks
overwhelmingly debunk. The fast path is a LOOKUP, not a classifier; never report
its verdict accuracy without that distribution beside it.
"""

from __future__ import annotations

import ast
from typing import Final

REFUTED: Final = "Refuted"
SUPPORTED: Final = "Supported"
CONFLICTING: Final = "Conflicting"
NEI: Final = "NEI"

# Exact, lowercased, whitespace-stripped. Built from the measured head of the
# 78,077-fact-check pool, widest-covering strings first within each block.
RATING_TO_VERDICT: Final[dict[str, str]] = {
    # -- the claim is false -------------------------------------------------
    "false": REFUTED,
    "falso": REFUTED,
    "mostly false": REFUTED,
    # Turkish dotless i, which is what the data actually contains.
    "yanlış": REFUTED,  # noqa: RUF001
    "yanlis": REFUTED,
    "faux": REFUTED,
    "fake": REFUTED,
    "fałsz": REFUTED,
    "falsch": REFUTED,
    "fals": REFUTED,
    "falsk": REFUTED,
    "nepravda": REFUTED,
    "notizia falsa": REFUTED,
    "netačno": REFUTED,
    "pants on fire": REFUTED,
    "salah": REFUTED,
    "tak benar": REFUTED,
    "disinformation": REFUTED,
    "onwaar": REFUTED,
    "onjuist": REFUTED,
    "vals": REFUTED,
    "hamis": REFUTED,
    "epätosi": REFUTED,
    "errado": REFUTED,
    "rrenë": REFUTED,
    "incorrect": REFUTED,
    "inaccurate": REFUTED,
    "untrue": REFUTED,
    "ψευδές": REFUTED,
    "невярно": REFUTED,
    "مضلل": CONFLICTING,          # "misleading" -- see the docstring
    "خطأ": REFUTED,
    "زائف": REFUTED,
    "असत्य": REFUTED,
    # fabricated media is a false claim about what the media shows
    "altered": REFUTED,
    "altered image": REFUTED,
    "montagem": REFUTED,
    "montaje": REFUTED,
    "fake tweet": REFUTED,
    # -- the claim is true --------------------------------------------------
    "true": SUPPORTED,
    "doğru": SUPPORTED,
    "prawda": SUPPORTED,
    "pravda": SUPPORTED,
    "verdadero": SUPPORTED,
    "verdadeiro": SUPPORTED,
    "correct": SUPPORTED,
    "waar": SUPPORTED,
    # -- partly true, cherrypicked, or stripped of context ------------------
    "half true": CONFLICTING,
    "partly false": CONFLICTING,
    "partly true": CONFLICTING,
    "partiellement faux": CONFLICTING,
    "mixture": CONFLICTING,
    "misleading": CONFLICTING,
    "engañoso": CONFLICTING,
    "enganoso": CONFLICTING,
    "enganyós": CONFLICTING,
    "és enganyós": CONFLICTING,
    "trompeur": CONFLICTING,
    "irreführend": CONFLICTING,
    "misleidend": CONFLICTING,
    "keliru": CONFLICTING,
    "sesat": CONFLICTING,
    "भ्रामक": CONFLICTING,
    "παραπληροφόρηση": CONFLICTING,
    "подвеждащо": CONFLICTING,
    "missing context": CONFLICTING,
    "out of context": CONFLICTING,
    "fuori contesto": CONFLICTING,
    "sem contexto": CONFLICTING,
    "sin contexto": CONFLICTING,
    "falta contexto": CONFLICTING,
    "محتوى ناقص": CONFLICTING,
    "عنوان مضلل": CONFLICTING,
    # -- nobody could establish it -----------------------------------------
    # -- a second pass, added after measuring the unmapped tail -------------
    # Every one of these is a dictionary cognate of a string already above, and
    # each was in the top 25 of the unmapped tail. Nineteen entries bought
    # **+0.2 points** on dev gold (81.7% -> 81.9%) and +0.9 on the pool
    # (78.3% -> 79.2%). That is the empirical case for stopping: the tail is
    # 13,583 distinct strings whose largest count is 140, so it is flat rather
    # than long, and there is no head left to take.
    "falsa": REFUTED,
    "yanliş": REFUTED,
    "ψευδες": REFUTED,
    "фейк": REFUTED,
    "really_false": REFUTED,
    "altered video": REFUTED,
    "immagine modificata": REFUTED,
    "distorcido": REFUTED,
    "parcialmente falso": CONFLICTING,
    "zavádějící": CONFLICTING,
    "zavádzajúce": CONFLICTING,
    "înșelător": CONFLICTING,
    "παραπλανητικό": CONFLICTING,
    "mengelirukan": CONFLICTING,
    "félrevezető": CONFLICTING,
    "contexte manquant": CONFLICTING,
    "manque de contexte": CONFLICTING,
    "fehlender kontext": CONFLICTING,
    "nedostaje kontekst": CONFLICTING,
    "unverifiable": NEI,
    "unproven": NEI,
    "unsupported": NEI,
    "no evidence": NEI,
    "not enough experts": NEI,
    "neoveriteľné": NEI,
    "sin registro": NEI,
    "cuestionable": NEI,
    "questionable": NEI,
}


def parse_ratings(raw: str | None) -> list[str]:
    """The `ratings` cell as a list of lowercased labels.

    The column holds a Python list literal. A cell that will not parse is
    treated as one label rather than dropped, because a publisher whose rating
    happens to contain a quote is still a rating.
    """
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        parsed = text
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, (list, tuple)):
        return []
    return [str(v).strip().lower() for v in parsed if str(v).strip()]


def rating_to_verdict(ratings: str | list[str] | None) -> str | None:
    """One verdict from a fact-check's ratings, or None to decline.

    None means "the fast path cannot answer this one" and the orchestrator falls
    through to the evidence path. It never means NEI: a fast path that answers
    "not enough evidence" is strictly worse than actually going and looking.
    """
    labels = parse_ratings(ratings) if isinstance(ratings, str) else list(ratings or [])
    mapped = {RATING_TO_VERDICT[label] for label in
              (str(x).strip().lower() for x in labels)
              if label in RATING_TO_VERDICT}
    if len(mapped) != 1:
        # Zero: the tail, which is 39 languages of long-tail publisher wording.
        # Two or more: the publishers disagree, which is not evidence for either.
        return None
    return mapped.pop()


def publisher_from_url(url: str | None) -> str | None:
    """The domain, minus `www.`, as the publisher name.

    MultiClaim has no publisher column; `instances` holds
    `[(timestamp, url), ...]` and the domain is the only publisher identity in
    the data. FR-8's answer is "Already checked by X", so X has to come from
    somewhere and this is the honest somewhere.
    """
    if not url:
        return None
    rest = url.split("://", 1)[-1]
    domain = rest.split("/", 1)[0].split("?", 1)[0].strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def first_instance_url(raw: str | None) -> str | None:
    """The first URL out of the `instances` column, which is
    `[(timestamp, url), ...]`."""
    if not raw or not raw.strip():
        return None
    try:
        parsed = ast.literal_eval(raw.strip())
    except (ValueError, SyntaxError):
        return None
    for item in parsed if isinstance(parsed, (list, tuple)) else []:
        if isinstance(item, (list, tuple)) and len(item) >= 2 and item[1]:
            return str(item[1])
        if isinstance(item, str) and item.startswith("http"):
            return item
    return None
