"""Rule-based check-worthiness and claim extraction (FR-6, FR-7).

The second implementation `SYSTEM_DESIGN.md` §3 requires of every stage by the
phase that introduces its model -- and the floor the trained span model has to
beat. No weights, no GPU, no download, so it runs in CI and it runs when the
adapter is missing.

## What "check-worthy" means here

`NFR-9`: opinions, predictions and value judgements route to `NotAClaim`, and
`PRD.md` scenario S4 makes "Good morning, stay blessed" the worked example. So
the question is not "is this true" but "is there anything here a fact-checker
could look up".

The rules are deliberately few. Each one is a property of the text that can be
checked without understanding it, and each targets a category the collection
brief asked for:

  too short         a three-word message carries no checkable assertion
  greeting-only     "Suprabhat", "Sat Sri Akal", "Good morning" and their kin
  blessing          optative constructions -- a wish about the world, not an
                    assertion about it: "Rabb sabnu khush rakhe"
  chain-request     "forward to 10 people", "share with everyone" -- an
                    instruction, not an assertion
  no content word   after stripping greetings, emoji and chain requests, a
                    message with nothing left is not making a claim

**They do not work, and the measurement is the point.** On the hand-typed 100
this implementation catches **0 of 15** real no-claim messages and ties
`majority_class` exactly at macro-F1 0.4595. The rules catch messages that are
short or empty; a blessing is neither. "Sat Sri Akal ji, Rabb sabnu khush rakhe,
ehna sandesh dostan nu bhejo" is fluent, complete, full of content words and
asserts nothing, so every rule here passes it through. That limitation is pinned
by a test that fails loudly if a future change fixes it, rather than left as a
comment. The arm that does work is `claims/nli_zeroshot.py`, which catches 7 of
15 -- see the project log. This one remains the floor `SYSTEM_DESIGN.md` §3 asks
for, and a floor is still worth having a number for.

Numbers and named entities are NOT used as evidence of check-worthiness. It is
tempting -- most viral health and scheme forwards carry a figure -- but "Rabb
sabnu khush rakhe, 11 logo ko bhejo" has a number in it and is the canonical
negative. Leaning on digits would score well on this data for the wrong reason.
"""

from __future__ import annotations

import re

from pipeline.contracts import MAX_CLAIMS, Claim, Trace
from preprocess.clean import strip_artefacts

# Below this many word characters there is nothing to check. Tuned on the
# hand-typed set's negatives, which bottom out around 6 tokens.
MIN_TOKENS = 4

# Greetings and blessings, across the three languages and both scripts. These
# are whole-message patterns: a greeting at the START of a message that goes on
# to make a claim must not suppress the claim, which is why each is anchored and
# stripped rather than used as a veto.
_GREETING = re.compile(
    r"(good\s+(morning|night|evening|day)|suprabhat|su\s?prabhat|namaste|namaskar"
    r"|sat\s+sri\s+akal|jai\s+(hind|shree\s+ram|mata\s+di)|shubh\s+\w+"
    r"|happy\s+\w+day|सुप्रभात"
    r"|नमस्ते|ਸਤ ਸ੍ਰੀ ਅਕਾਲ)",
    re.IGNORECASE,
)

# Blessings and well-wishes. A distinct category from greetings and a named one
# in docs/collection-brief.md, which asked collectors for "greetings, blessings,
# jokes, pure opinion" as the no-claim bucket.
#
# What unites them grammatically is the optative: they express a wish about the
# world rather than an assertion about it. "Rabb sabnu khush rakhe" and "aapki
# manokamna puri hogi" describe nothing that could be looked up. Matching the
# construction is why this is a rule and not a word list.
_BLESSING = re.compile(
    r"((rabb|allah|bhagwan|waheguru|god|ishwar|khuda)\s+\w*\s*"
    r"(rakhe|kare|karen|deve|de|bless|rakkhe|rakhe)"
    r"|mangalmay|manokamna|khush\s+rakhe|sukhi\s+raho|salamat\s+raho"
    r"|have\s+a\s+\w+\s+day|stay\s+(blessed|positive|safe|happy)"
    r"|(puri|poori)\s+hogi|barkat|\w+\s+mubarak"
    r"|खुश\s+रखे|मंगलमय)",
    re.IGNORECASE,
)

# Chain-letter instructions. An instruction is not an assertion.
_CHAIN = re.compile(
    r"(forward\s+(this|to|karo|kar\s+do|sabko)|share\s+(this|with|karo)"
    r"|send\s+to\s+\d+|\d+\s+(logo|people|friends|dostan)\s+(ko|nu|to)?\s*(bhej|send)"
    r"|sabko\s+bhej|sareyan\s+nu\s+dass|bhejein|forward\s+many\s+times)",
    re.IGNORECASE,
)

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿️‍]"
)

_WORD = re.compile(r"[\wऀ-ॿ਀-੿]+", re.UNICODE)

# Sentence boundaries. The danda ends a sentence in Devanagari and Gurmukhi;
# splitting on "." alone would treat a whole Hindi forward as one sentence.
_SENTENCE = re.compile(r"(?<=[.!?।])\s+|\n+")


def _residue(text: str) -> str:
    """What is left after greetings, chain requests and emoji are removed."""
    out = _GREETING.sub(" ", text)
    out = _BLESSING.sub(" ", out)
    out = _CHAIN.sub(" ", out)
    out = _EMOJI.sub(" ", out)
    return " ".join(out.split())


def is_check_worthy(text: str) -> bool:
    """True if there is anything here a fact-checker could look up."""
    cleaned = strip_artefacts(text or "")
    if not cleaned.strip():
        return False
    if len(_WORD.findall(cleaned)) < MIN_TOKENS:
        return False
    residue = _residue(cleaned)
    return len(_WORD.findall(residue)) >= MIN_TOKENS


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text or "") if s.strip()]


class HeuristicClaims:
    """Rules only. The floor `SYSTEM_DESIGN.md` §3 asks every stage to have."""

    name = "claims"
    impl = "heuristic"

    def check_worthy(self, trace: Trace) -> bool:
        return bool(trace.pre) and is_check_worthy(trace.pre.normalized)

    def extract(self, trace: Trace) -> Trace:
        """Each check-worthy sentence is a claim, longest first, capped at 3.

        Longest first rather than in order, because FR-7 caps the number
        verified at 3 and the remainder is only listed. When something has to be
        dropped, dropping the shortest fragment loses least.
        """
        assert trace.pre is not None
        text = trace.pre.normalized
        sentences = [s for s in split_sentences(text) if is_check_worthy(s)]
        if not sentences:
            sentences = [text]
        ranked = sorted(sentences, key=len, reverse=True)

        trace.claims = [
            Claim(claim_id=f"c{i}", text=s, span=_locate(text, s))
            for i, s in enumerate(ranked[:MAX_CLAIMS], start=1)
        ]
        trace.unchecked_claims = ranked[MAX_CLAIMS:]
        return trace


def _locate(haystack: str, needle: str) -> tuple[int, int] | None:
    """Character offsets of `needle` in `haystack`, per the `Claim.span` contract."""
    start = haystack.find(needle)
    return (start, start + len(needle)) if start >= 0 else None
