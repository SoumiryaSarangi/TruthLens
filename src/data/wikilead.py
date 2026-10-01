"""Lead sections from a MediaWiki XML dump, with the standard library only.

The demo corpus's encyclopedia half (SYSTEM_DESIGN.md §14, decision D7) is the
LEAD section of every Hindi and Punjabi article: the text before the first
`== heading ==`. Leads carry what Wikipedia is good for here -- who a minister
is, what a scheme is -- at about 5% of the cost of full articles.

No wikitext library is installed (mwparserfromhell, mwxml and wikitextparser
are all absent), and a lead needs none of what they do well: it is prose plus
templates, links, references and the occasional table. So this is a regex
stripper, written to be wrong in the safe direction. Anything it cannot read as
prose is DROPPED rather than kept, because a passage the stance model reads is
better short than full of `{{Infobox` debris.

Pure functions over strings and file objects; `tests/test_wikilead.py` runs
them on hand-written wikitext, no dump needed.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import quote

# Leads are capped, then cut back to a sentence end. 1,200 characters is about
# what BGE-M3 sees at 256 tokens of Devanagari, so the passage the stance model
# reads is the same text the retriever matched -- the rule `hybrid.py` keeps.
MAX_CHARS = 1_200
# Below this the "lead" is a stub line or the leftovers of a page that was all
# template ("X may refer to:" disambiguation pages strip to almost nothing).
MIN_CHARS = 60

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_REF_PAIR = re.compile(r"<ref\b[^>/]*>.*?</ref\s*>", re.DOTALL | re.IGNORECASE)
_REF_SELF = re.compile(r"<ref\b[^>]*/>", re.IGNORECASE)
# Whole blocks whose content is never prose.
_BLOCK = re.compile(
    r"<(gallery|math|syntaxhighlight|source|score|timeline|imagemap|mapframe|"
    r"graph|templatedata|references)\b[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_TABLE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_LINK = re.compile(r"\[\[([^\[\]]*)\]\]")
_EXTERNAL = re.compile(r"\[(?:https?:)?//[^\s\]]+(?:\s+([^\]]*))?\]")
_BARE_URL = re.compile(r"https?://\S+")
_QUOTES = re.compile(r"'{2,}")
_MAGIC = re.compile(r"__[A-Z]+__")
_HEADING = re.compile(r"^=+.*?=+\s*$", re.MULTILINE)
_LIST_MARK = re.compile(r"^[*#:;]+\s*", re.MULTILINE)
_SPACE = re.compile(r"[ \t\u00a0]+")
_SENTENCE_END = re.compile(r"[.!?\u0964\u0965](?=\s|$)")    # ।  ॥


def lead_wikitext(wikitext: str) -> str:
    """Everything before the first section heading."""
    match = _HEADING.search(wikitext)
    return wikitext[:match.start()] if match else wikitext


def _innermost(pattern: re.Pattern, repl, text: str, limit: int = 50) -> str:
    """Apply an innermost-first substitution until nothing changes.

    Templates and links nest (`{{a|{{b}}}}`, `[[File:x|[[link]]]]`), and a
    single regex cannot match balanced brackets. Replacing the innermost level
    repeatedly does. `limit` bounds pathological input; whatever survives it is
    cleaned up by the debris check in `strip_markup`.
    """
    for _ in range(limit):
        new = pattern.sub(repl, text)
        if new == text:
            return new
        text = new
    return text


def _link(match: re.Match) -> str:
    """[[target|label]] -> label; [[target]] -> target; namespaced -> dropped.

    A target with a colon is a namespace (File:, Category:, चित्र:, ਸ਼੍ਰੇਣੀ:, an
    interwiki) in every language, and none of those is prose. Dropping on the
    colon avoids keeping a list of localised namespace names that would always
    be incomplete. Article titles with a colon exist but are rare in leads.
    """
    inner = match.group(1)
    target, _, label = inner.partition("|")
    if ":" in target:
        return ""
    return (label.rsplit("|", 1)[-1] if label else target).strip()


def strip_markup(wikitext: str) -> str:
    """Wikitext -> plain prose. Unreadable constructs are removed, not kept."""
    text = _COMMENT.sub("", wikitext)
    text = _BLOCK.sub("", text)
    text = _REF_PAIR.sub("", text)
    text = _REF_SELF.sub("", text)
    text = _innermost(_TEMPLATE, "", text)
    text = _TABLE.sub("", text)
    text = _innermost(_LINK, _link, text)
    text = _EXTERNAL.sub(lambda m: m.group(1) or "", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _BARE_URL.sub("", text)
    text = _QUOTES.sub("", text)
    text = _MAGIC.sub("", text)
    text = _LIST_MARK.sub("", text)

    lines = []
    for line in text.splitlines():
        line = _SPACE.sub(" ", line).strip()
        # Debris from an unbalanced template or table: drop the line.
        if not line or line.startswith(("|", "{", "}", "!")) or "{{" in line or "}}" in line:
            continue
        lines.append(line)
    text = " ".join(lines)
    # "( )" and "(, )" are what is left of a parenthesis whose contents were all
    # templates -- typically a pronunciation or a date of birth.
    text = re.sub(r"\(\s*[,;]?\s*\)", "", text)
    text = re.sub(r"\s+([,.;:\u0964])", r"\1", text)
    return _SPACE.sub(" ", text).strip()


def cap(text: str, max_chars: int = MAX_CHARS) -> str:
    """Cut to at most `max_chars`, at the last sentence end if there is one in
    the second half, else at whitespace."""
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    ends = [m.end() for m in _SENTENCE_END.finditer(head)]
    if ends and ends[-1] >= max_chars // 2:
        return head[:ends[-1]].strip()
    space = head.rfind(" ")
    return head[:space].strip() if space > 0 else head


def lead(wikitext: str, max_chars: int = MAX_CHARS) -> str:
    """The article's lead as plain prose, capped; "" if too short to keep."""
    text = cap(strip_markup(lead_wikitext(wikitext)), max_chars)
    return text if len(text) >= MIN_CHARS else ""


# -----------------------------------------------------------------------------
# The dump
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Page:
    page_id: str
    title: str
    namespace: int
    redirect: bool
    wikitext: str


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def iter_pages(stream: BinaryIO) -> Iterator[Page]:
    """Every <page> in a MediaWiki export, streamed.

    `iterparse` with each page cleared after use, so memory stays flat
    over a dump that decompresses to gigabytes. The export namespace URI changes
    between dump versions (export-0.10, -0.11), so tags are matched by local name.
    """
    root = None
    for event, elem in ET.iterparse(stream, events=("start", "end")):
        if root is None:
            root = elem
        if event != "end" or _local(elem.tag) != "page":
            continue
        fields: dict[str, str] = {}
        redirect = False
        for child in elem:
            name = _local(child.tag)
            if name in ("title", "ns", "id"):
                fields[name] = child.text or ""
            elif name == "redirect":
                redirect = True
            elif name == "revision":
                for part in child:
                    if _local(part.tag) == "text":
                        fields["text"] = part.text or ""
        yield Page(
            page_id=fields.get("id", ""),
            title=fields.get("title", ""),
            namespace=int(fields.get("ns") or 0),
            redirect=redirect,
            wikitext=fields.get("text", ""),
        )
        # Clearing the page alone still leaves one empty child per page on the
        # root -- ~200k of them; clearing the root drops those too.
        elem.clear()
        root.clear()


def article_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
