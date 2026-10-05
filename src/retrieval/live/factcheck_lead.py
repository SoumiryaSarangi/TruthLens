"""The opening paragraph of a published fact-check, quoted on a fast-path answer.

docs/factcheck-lead-protocol.md fixes the rules. One GET of the article's public URL (the one the card links to);
no text of the reader's message is sent. Stdlib HTML handling, a disk cache, a short timeout, and any failure is
simply "no lead": the card shows nothing extra and nothing else changes.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

CACHE_DIR = Path("data/interim/live_cache/factcheck_lead")      # gitignored, like all of data/interim
TIMEOUT_S = 4.0
MIN_CHARS = 60
MAX_CHARS = 300
MAX_BYTES = 400_000
USER_AGENT = "TruthLens-student-project/1.0 (reads the opening paragraph of a fact-check the user is shown a link to)"
BOILERPLATE = re.compile(r"cookie|subscribe|sign in|log in|newsletter|javascript|all rights reserved|enable js", re.I)
_SKIP = {"script", "style", "nav", "footer", "header", "aside", "noscript", "form", "button"}


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.paragraphs: list[str] = []
        self._skip = 0
        self._in_title = False
        self._in_p = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:description", "description") and a.get("content"):
                self.meta.setdefault(key, a["content"])
        elif tag == "title":
            self._in_title = True
        elif tag in _SKIP:
            self._skip += 1
        elif tag == "p" and not self._skip:
            self._in_p, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in _SKIP and self._skip:
            self._skip -= 1
        elif tag == "p" and self._in_p:
            self._in_p = False
            self.paragraphs.append(" ".join("".join(self._buf).split()))

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_p and not self._skip:
            self._buf.append(data)


def _clean(text: str) -> str:
    return " ".join(html.unescape(text or "").split())


def _usable(text: str, title: str) -> bool:
    if len(text) < MIN_CHARS or BOILERPLATE.search(text):
        return False
    t = _clean(title).lower()
    return not (t and (text.lower() == t or text.lower() in t))


def _cut(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    return re.sub(r"\s+\S*$", "", text[:MAX_CHARS]) + "…"


def extract_lead(page_html: str, title_hint: str = "") -> str | None:
    """The first usable paragraph of an article page, or None (see the protocol for the rules)."""
    parser = _Page()
    try:
        parser.feed(page_html)
    except Exception:
        return None
    title = _clean(parser.title) or title_hint
    candidates = [_clean(parser.meta.get("og:description", "")), _clean(parser.meta.get("description", "")), *parser.paragraphs]
    for text in candidates:
        if _usable(text, title):
            return _cut(text)
    return None


# docs/factcheck-finding-protocol.md: the first sentence that states a finding about the claim.
CUES = re.compile(
    r"found that|no evidence|not true|false|fake|misleading|doctored|edited|fabricated|baseless|hoax|debunk"
    r"|there is no|has no|have no|does not|did not|is not|was not|not a |not an |actually|in fact|old video"
    r"|old image|unrelated|satire|no such|untrue|incorrect|unverified|not found|no record|clarified|denied", re.I)
MIN_SENTENCE, MAX_SENTENCE, MAX_PARAGRAPHS = 40, 300, 25
_SENTENCES = re.compile(r"(?<=[.!?])\s+")


def extract_finding(page_html: str, title_hint: str = "") -> str | None:
    """The first sentence of the article that states a finding (a conclusion cue), or None."""
    parser = _Page()
    try:
        parser.feed(page_html)
    except Exception:
        return None
    title = (_clean(parser.title) or title_hint).lower()
    for paragraph in parser.paragraphs[:MAX_PARAGRAPHS]:
        for sentence in _SENTENCES.split(_clean(paragraph)):
            if (MIN_SENTENCE <= len(sentence) <= MAX_SENTENCE and CUES.search(sentence)
                    and not BOILERPLATE.search(sentence) and not (title and sentence.lower() in title)):
                return sentence
    return None


def fetch_finding(url: str, title_hint: str = "", cache_dir: Path | str = CACHE_DIR / "finding", timeout: float = TIMEOUT_S) -> str | None:
    """`fetch_lead` with the finding extractor (separate cache directory)."""
    return fetch_lead(url, title_hint, cache_dir, timeout, extractor=extract_finding)


def fetch_lead(url: str, title_hint: str = "", cache_dir: Path | str = CACHE_DIR, timeout: float = TIMEOUT_S,
               extractor=None) -> str | None:
    """GET the page and extract its lead. Cached (a page that answered but had no lead too; a network failure is not)."""
    if not re.match(r"^https?://", url or ""):
        return None
    cache = Path(cache_dir)
    path = cache / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".json")
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8")).get("lead")
    except (OSError, ValueError):
        pass
    lead = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            lead = (extractor or extract_lead)(resp.read(MAX_BYTES).decode(charset, errors="replace"), title_hint)
    except Exception:
        return None                                           # not cached: a network blip must not be remembered
    try:
        cache.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"url": url, "lead": lead}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return lead
