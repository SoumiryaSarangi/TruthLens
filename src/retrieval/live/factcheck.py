"""Google Fact Check Tools API: published fact-checks of the claim, live.

`GET https://factchecktools.googleapis.com/v1alpha1/claims:search` returns
claims with their reviews: who reviewed it, the headline, the URL and the
publisher's own rating. It covers what Wikipedia cannot -- viral FALSE claims
(Wikipedia rarely states a rumour; fact-checkers write about it) -- and is the
live twin of the offline fast path over 78,077 fact-checks.

**The key** comes from the environment (`GOOGLE_FACTCHECK_API_KEY`) or a
git-ignored `.env`. It is never logged, cached, traced or put in an error:
`http.redact` strips it from every URL that is stored or shown. Without a key
this source reports itself unavailable and the pipeline uses Wikipedia alone.

Two things from the offline pipeline carry over unchanged (project log, lessons
15 and the fast-path findings):
- a review's CLAIM text states the rumour as fact, so it is used only to decide
  whether this review is about OUR claim (BGE-M3 cosine against tau_match); what
  the stance model reads, if the review is not a fast-path hit, is its HEADLINE;
- the publisher's rating becomes a verdict only through `rating_to_verdict`, and
  a rating it cannot map, or ratings that disagree, are declined -- never guessed.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from retrieval.live.http import Fetcher

API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
ENV_VAR = "GOOGLE_FACTCHECK_API_KEY"
_LINE = re.compile(rf"^\s*{ENV_VAR}\s*=\s*(.*?)\s*$")


@dataclass(frozen=True)
class FactCheckHit:
    claim_text: str          # the claim as the publisher quoted it (a rumour)
    publisher: str
    title: str               # the review's headline
    url: str
    rating: str              # the publisher's textual rating, e.g. "False"
    lang: str


def load_key(env: dict[str, str] | None = None, dotenv: Path | str = ".env") -> str | None:
    """The API key from the environment, else from `.env`; None if neither has one."""
    source = os.environ if env is None else env
    if key := source.get(ENV_VAR, "").strip():
        return key
    path = Path(dotenv)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if (m := _LINE.match(line)) and m.group(1).strip("'\""):
                return m.group(1).strip("'\"")
    return None


class GoogleFactCheck:
    name = "google_factcheck"

    def __init__(self, fetcher: Fetcher | None = None, key: str | None = None,
                 page_size: int = 10) -> None:
        self.fetcher = fetcher or Fetcher()
        self._key = key if key is not None else load_key()
        self.page_size = page_size

    @property
    def available(self) -> bool:
        return bool(self._key)

    def search(self, query: str) -> list[FactCheckHit]:
        if not self.available:
            return []
        url = (f"{API}?pageSize={self.page_size}&query={urllib.parse.quote(query)}"
               f"&key={urllib.parse.quote(self._key)}")
        hits: list[FactCheckHit] = []
        for claim in self.fetcher.get_json(url).get("claims", []):
            for review in claim.get("claimReview", []):
                hits.append(FactCheckHit(
                    claim_text=claim.get("text", ""),
                    publisher=(review.get("publisher") or {}).get("name")
                    or (review.get("publisher") or {}).get("site", ""),
                    title=review.get("title", ""),
                    url=review.get("url", ""),
                    rating=review.get("textualRating", ""),
                    lang=review.get("languageCode", "")[:2],
                ))
        return hits
