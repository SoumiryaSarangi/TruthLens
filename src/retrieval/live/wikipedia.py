"""Live Wikipedia evidence (MediaWiki API; text is CC BY-SA, so every passage keeps its URL).

Per language: ONE search call (top 5 titles, with the query-matched snippet) and
ONE batched extract call for the leads. The spike that preceded this made ~10
calls per claim and was rate-limited; this makes 2-3 per language.

**The query is an OR query.** CirrusSearch ANDs terms by default, so one garbled
word ("banwaya" from a romanised verb) returned nothing relevant -- the first
spike's Taj Mahal query found an Asha Bhosle song list. OR returns a broad
candidate set and `LiveEvidence` re-ranks it with BGE-M3, which reads meaning
across languages where Wikipedia's lexical search cannot.

**A passage is the lead plus the search snippet.** The lead says what the page is
about; the snippet is the matched excerpt from anywhere in the article, which is
where "chief minister of Gujarat from 2001 to 2014" lives for a page whose lead
is about the Prime Minister.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass

from pipeline.relevance import STOPWORDS, content_terms
from retrieval.live.http import Fetcher

API = "https://{lang}.wikipedia.org/w/api.php"
LANGS = ("en", "hi", "pa")
MAX_TERMS = 8
DEEP_PER_SEARCH = 8        # retrieval v2: titles per query (v1: 5)
MAX_ACRONYMS = 3           # retrieval v2: acronyms resolved per claim
MAX_PHRASES = 2            # retrieval v2: proper-noun phrases in the entity query
ACRONYM_TITLES = 2         # retrieval v2: titles taken from a search of an acronym alone
LEAD_CHARS = 700
SNIPPET_CHARS = 500
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class WikiCandidate:
    title: str
    lang: str
    url: str
    text: str            # lead + snippet, what the stance model reads


def build_queries(forms: list[str], lang_hint: str) -> list[tuple[str, str]]:
    """(wikipedia language, OR query) for each form of the claim.

    A Latin form searches English Wikipedia (names survive romanisation); a
    native-script form searches that language's Wikipedia. Duplicates collapse.
    """
    seen, out = set(), []
    for form in forms:
        terms = sorted(content_terms(form))[:MAX_TERMS]
        if not terms:
            continue
        lang = "en" if form.isascii() else (lang_hint if lang_hint in LANGS else "en")
        key = (lang, tuple(terms))
        if key not in seen:
            seen.add(key)
            out.append((lang, " OR ".join(terms)))
    return out


_PHRASE_JOIN = frozenset({"of", "the", "and", "for", "de"})
_CAP_WORD = re.compile(r"[A-Z][\w'\u2019-]*")
_ACRONYM = re.compile(r"^[A-Z]{3,6}$")
# Capitalised only because they open a sentence or are shouted: never an entity or an acronym.
_NOT_ENTITY = STOPWORDS | frozenset({"the", "a", "an", "if", "since", "when", "now", "all", "any", "do", "does", "is", "are", "was", "it",
                         "this", "that", "yes", "no", "ok", "pls", "plz", "fake", "true", "false", "note", "alert", "urgent", "new",
                         "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                         "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"})


def entity_phrases(text: str, limit: int = MAX_PHRASES) -> list[str]:
    """Runs of capitalised words ('Atal Pension Yojana', 'Reserve Bank of India'), longest first.

    Wikipedia's search ANDs quoted phrases, so a claim that names a thing finds the page about the thing,
    where eight ORed content words find the pages that merely contain many of them. Acronyms are left to
    `acronyms` (they are searched alone). A word that is capitalised only because it opens the sentence is skipped.
    """
    tokens = [re.sub(r"['\u2019]s$", "", t) for t in re.findall(r"[\w'\u2019-]+", text)]
    phrases: list[list[str]] = []
    run: list[str] = []
    for i, tok in enumerate(tokens):
        is_cap = bool(_CAP_WORD.fullmatch(tok)) and not _ACRONYM.match(tok) and not (i == 0 and tok.lower() in _NOT_ENTITY)
        if (is_cap and tok.lower() not in _NOT_ENTITY) or (run and tok.lower() in _PHRASE_JOIN and i + 1 < len(tokens) and _CAP_WORD.fullmatch(tokens[i + 1])):
            run.append(tok)
        else:
            if run:
                phrases.append(run)
            run = []
    if run:
        phrases.append(run)
    seen, out = set(), []
    for words in sorted((p for p in phrases if len(" ".join(p)) >= 4), key=lambda p: -len(" ".join(p))):
        phrase = " ".join(words)
        if phrase.lower() not in seen:
            seen.add(phrase.lower())
            out.append(phrase)
    return out[:limit]


def acronyms(forms: list[str], limit: int = MAX_ACRONYMS) -> list[str]:
    """All-capital tokens of 3 to 6 letters (UPI, OTP, PMJDY), in order of first appearance, from every form of the claim."""
    seen: list[str] = []
    for form in forms:
        for tok in re.findall(r"[A-Za-z]+", form):
            if _ACRONYM.match(tok) and tok.lower() not in _NOT_ENTITY and tok not in seen:
                seen.append(tok)
    return seen[:limit]


def build_queries_v2(forms: list[str], lang_hint: str) -> list[tuple]:
    """Retrieval v2 (docs/live-retrieval-v2-protocol.md, stage 1): the v1 OR queries, kept and deepened, plus an
    entity query and one query per acronym. Each item is (language, query, titles to take).

    Every query is English Wikipedia except the v1 native-script one. The union is re-ranked by BGE-M3 exactly as
    in v1 and the same grounding gate decides what is judged: nothing here loosens a gate.
    """
    out: list[tuple] = [(lang, query, DEEP_PER_SEARCH) for lang, query in build_queries(forms, lang_hint)]
    latin = [f for f in forms if f.isascii()]
    phrases = entity_phrases(latin[-1]) if latin else []      # the English form is last (see the orchestrator)
    if phrases:
        out.append(("en", " ".join(f'"{p}"' for p in phrases), DEEP_PER_SEARCH))
    for acro in acronyms(latin):
        out.append(("en", acro, ACRONYM_TITLES))
    seen, unique = set(), []
    for item in out:
        key = (item[0], item[1])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _clean(text: str) -> str:
    return " ".join(html.unescape(_TAGS.sub("", text or "")).split())


def page_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"


class WikipediaLive:
    name = "wikipedia"

    def __init__(self, fetcher: Fetcher | None = None, per_search: int = 5) -> None:
        self.fetcher = fetcher or Fetcher()
        self.per_search = per_search

    def _search(self, lang: str, query: str, limit: int | None = None) -> list[dict]:
        url = (API.format(lang=lang) + "?action=query&list=search&format=json"
               f"&srlimit={limit or self.per_search}&srprop=snippet&srsearch={urllib.parse.quote(query)}")
        return self.fetcher.get_json(url).get("query", {}).get("search", [])

    def _leads(self, lang: str, titles: list[str]) -> dict[str, str]:
        if not titles:
            return {}
        url = (API.format(lang=lang) + "?action=query&format=json&prop=extracts&exintro=1"
               "&explaintext=1&exlimit=max&redirects=1&titles="
               + urllib.parse.quote("|".join(titles)))
        pages = self.fetcher.get_json(url).get("query", {}).get("pages", {})
        return {p["title"]: _clean(p.get("extract", "")) for p in pages.values() if "title" in p}

    def _english_titles(self, lang: str, titles: list[str]) -> dict[str, str]:
        """English page title for each `lang` title that has one (language links)."""
        if not titles:
            return {}
        url = (API.format(lang=lang) + "?action=query&format=json&prop=langlinks&lllang=en"
               "&lllimit=max&redirects=1&titles=" + urllib.parse.quote("|".join(titles)))
        pages = self.fetcher.get_json(url).get("query", {}).get("pages", {})
        return {p["title"]: p["langlinks"][0]["*"] for p in pages.values()
                if p.get("langlinks") and "title" in p}

    def search(self, queries: list[tuple], to_english: bool = False) -> list[WikiCandidate]:
        """Candidates for every (language, query), one fetch of leads per language.

        `to_english` swaps a hi/pa page for its English counterpart (language links)
        and reads the ENGLISH lead: the live verdict reads English, where the NLI
        model can tell "capital of India" from "capital of Maharashtra". A page with
        no English counterpart keeps its own text.
        """
        by_lang: dict[str, dict[str, str]] = {}
        for lang, query, *limit in queries:
            for hit in self._search(lang, query, limit[0] if limit else None):
                by_lang.setdefault(lang, {}).setdefault(hit["title"], _clean(hit.get("snippet", "")))
        out: list[WikiCandidate] = []
        if to_english:
            for lang in [lg for lg in by_lang if lg != "en"]:
                english = self._english_titles(lang, list(by_lang[lang]))
                for title in list(by_lang[lang]):
                    if title in english:
                        by_lang["en"] = by_lang.get("en", {})
                        by_lang["en"].setdefault(english[title], "")
                        del by_lang[lang][title]
            by_lang = {k: v for k, v in by_lang.items() if v}
        for lang, found in by_lang.items():
            leads = self._leads(lang, list(found))
            for title, snippet in found.items():
                lead = leads.get(title, "")[:LEAD_CHARS]
                text = f"{lead} … {snippet[:SNIPPET_CHARS]}" if snippet else lead
                if text.strip():
                    out.append(WikiCandidate(title, lang, page_url(lang, title), text))
        return out
