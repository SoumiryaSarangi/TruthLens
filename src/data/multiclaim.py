"""MultiClaim / SemEval-2025 Task 7 loader.

Three CSVs, supplied manually after Zenodo approval:

    fact_checks.csv              435,252 fact-checks
    posts.csv                     89,139 social media posts
    fact_check_post_mapping.csv  105,424 (post, fact-check) pairs

**Restricted, not redistributable.** The CSVs live in gitignored `data/raw/`;
only ID manifests reach `data/splits/`, exactly as for AVeriTeC and X-CLAIM.

The retrieval task this gives us: **a post is the query, and the fact-checks it
was paired with are the gold.** That is the claim-matching fast path evaluated
directly, and it is the first multilingual retrieval task in the project --
AVeriTeC is English-only and X-CLAIM is a span task with no relevance
judgements.

Several columns are Python list literals rather than plain strings, including
the language columns, so they are parsed rather than read.
"""

from __future__ import annotations

import ast
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from data.verdicts import (
    first_instance_url,
    parse_ratings,
    publisher_from_url,
    rating_to_verdict,
)

RAW = Path("data/raw/multiclaim")

# ISO 639-3 as MultiClaim reports it -> our language codes.
ISO_TO_LANG = {"eng": "en", "hin": "hi", "pan": "pa"}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


@dataclass(frozen=True)
class Post:
    post_id: str
    text: str
    lang: str | None          # None when the post is outside en/hi/pa


@dataclass(frozen=True)
class FactCheck:
    fact_check_id: str
    claim: str
    title: str
    lang: str | None
    # Phase 4 (FR-8). The fast path answers "Already checked by X: <title>" with
    # a verdict, and none of X, the link or the verdict existed in this loader
    # until then -- they live in the `ratings` and `instances` columns, which
    # nothing read. `verdict` is None when the publisher's rating is outside the
    # mapping, which makes the matcher decline rather than guess.
    ratings: tuple[str, ...] = ()
    url: str | None = None
    publisher: str | None = None
    verdict: str | None = None


def parse_listish(value: str | None) -> str | None:
    """Several MultiClaim columns hold a Python list literal, not a string.

    `claim` looks like `"('original text', 'english text', [('eng', 0.9)])"`,
    and the language columns like `"[('eng', 1.0)]"`. Returns the first usable
    scalar, or None.
    """
    if value is None or value == "":
        return None
    text = value.strip()
    if not (text.startswith("[") or text.startswith("(")):
        return text
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text
    while isinstance(parsed, (list, tuple)) and parsed:
        parsed = parsed[0]
    return None if parsed is None else str(parsed)


def _lang(value: str | None) -> str | None:
    iso = parse_listish(value)
    return ISO_TO_LANG.get(iso) if iso else None


def _text(value: str | None) -> str:
    """Post and claim text columns are `(original, english, [languages])`.

    The ORIGINAL is taken, never the English translation: the whole point of
    this project is performance on the language as written, and silently
    evaluating on machine-translated English would make the multilingual
    numbers meaningless.
    """
    if not value:
        return ""
    text = value.strip()
    if not text.startswith("("):
        return text
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text
    if isinstance(parsed, (list, tuple)) and parsed:
        return str(parsed[0] or "")
    return str(parsed)


def load_posts(langs: set[str] | None = None) -> dict[str, Post]:
    out: dict[str, Post] = {}
    with (RAW / "posts.csv").open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            lang = _lang(row.get("post_detected_language_iso"))
            if langs is not None and lang not in langs:
                continue
            text = _text(row.get("post_body")) or _text(row.get("ocr"))
            if not text.strip():
                continue
            out[str(row["post_id"])] = Post(str(row["post_id"]), text, lang)
    return out


def load_fact_checks(ids: set[str] | None = None) -> dict[str, FactCheck]:
    out: dict[str, FactCheck] = {}
    with (RAW / "fact_checks.csv").open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fc_id = str(row["fact_check_id"])
            if ids is not None and fc_id not in ids:
                continue
            ratings = parse_ratings(row.get("ratings"))
            url = first_instance_url(row.get("instances"))
            out[fc_id] = FactCheck(
                fc_id,
                _text(row.get("claim")),
                _text(row.get("title")),
                _lang(row.get("claim_detected_language_iso")),
                ratings=tuple(ratings),
                url=url,
                publisher=publisher_from_url(url),
                verdict=rating_to_verdict(ratings),
            )
    return out


def load_pairs() -> list[tuple[str, str, str]]:
    """(post_id, fact_check_id, relationship) for every annotated pair."""
    with (RAW / "fact_check_post_mapping.csv").open("r", encoding="utf-8", newline="") as fh:
        return [
            (str(r["post_id"]), str(r["fact_check_id"]), r.get("relationship", ""))
            for r in csv.DictReader(fh)
        ]
