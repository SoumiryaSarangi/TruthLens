"""One tokenizer, used by every lexical component.

Trivial, but it lives in one place on purpose: BM25 scoring documents with one
tokenizer while the paragraph selector uses another would produce rankings that
disagree with the passages shown as evidence for them.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    r"""Lowercased unicode word tokens.

    `\w+` keeps Devanagari and Gurmukhi intact, so the same function still
    works when Phase 2 brings non-English text through here.
    """
    return _WORD.findall(text.lower())
