"""Live Wikipedia and Google Fact Check clients (post-test Phase 7).

No network, key or model: a fake opener replays response shapes taken from the
real APIs, and a fake encoder gives two-word "topics" a controllable cosine.
"""

from __future__ import annotations

import io
import json
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from pipeline.live import LiveEvidence
from retrieval.live.factcheck import GoogleFactCheck, load_key
from retrieval.live.http import Fetcher, LiveError, redact
from retrieval.live.wikipedia import WikipediaLive, build_queries

KEY = "AIzaSy-SECRET-KEY-123"


class FakeOpener:
    """Routes a request to the first route whose substring is in the URL."""

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        for needle, outcome in self.routes:
            if needle in url:
                if isinstance(outcome, list):          # a sequence of outcomes, consumed in order
                    outcome = outcome.pop(0) if len(outcome) > 1 else outcome[0]
                if isinstance(outcome, Exception):
                    raise outcome
                return io.BytesIO(json.dumps(outcome).encode("utf-8"))
        raise AssertionError(f"no route for {redact(url)}")


def make_fetcher(tmp_path, routes, **kw):
    sleeps: list[float] = []
    opener = FakeOpener(routes)
    fetcher = Fetcher(cache_dir=tmp_path / "cache", opener=opener, sleep=sleeps.append,
                      min_gap_s=0.0, **kw)
    return fetcher, opener, sleeps


def http_error(code, retry_after=None):
    headers = Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return HTTPError("https://x", code, "err", headers, io.BytesIO(b"{}"))


# -- http.py -------------------------------------------------------------------


def test_redact_removes_the_key():
    assert KEY not in redact(f"https://x/api?query=q&key={KEY}")
    assert "key=***" in redact(f"https://x/api?query=q&key={KEY}&pageSize=3")


def test_a_cached_response_needs_no_network(tmp_path):
    fetcher, opener, _ = make_fetcher(tmp_path, [("example.org", {"a": 1})])
    assert fetcher.get_json("https://example.org/q") == {"a": 1}
    assert fetcher.get_json("https://example.org/q") == {"a": 1}
    assert len(opener.calls) == 1


def test_the_api_key_never_reaches_the_cache_directory(tmp_path):
    fetcher, _, _ = make_fetcher(tmp_path, [("example.org", {"ok": True})])
    fetcher.get_json(f"https://example.org/q?key={KEY}")
    stored = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "cache").glob("*.json"))
    assert KEY not in stored and "key=***" in stored


def test_a_429_is_retried_after_the_retry_after_header(tmp_path):
    fetcher, opener, sleeps = make_fetcher(
        tmp_path, [("example.org", [http_error(429, "2"), {"ok": 1}])])
    assert fetcher.get_json("https://example.org/q") == {"ok": 1}
    assert len(opener.calls) == 2 and 2.0 in sleeps


def test_a_client_error_is_not_retried(tmp_path):
    fetcher, opener, _ = make_fetcher(tmp_path, [("example.org", http_error(403))])
    with pytest.raises(LiveError, match="HTTP 403"):
        fetcher.get_json("https://example.org/q")
    assert len(opener.calls) == 1


def test_a_network_failure_degrades_to_liveerror_without_the_key(tmp_path):
    fetcher, _, _ = make_fetcher(tmp_path, [("example.org", URLError("down"))], retries=1)
    with pytest.raises(LiveError) as err:
        fetcher.get_json(f"https://example.org/q?key={KEY}")
    assert KEY not in str(err.value)


def test_requests_to_one_host_are_spaced(tmp_path):
    now = {"t": 0.0}
    sleeps: list[float] = []

    def sleep(s):
        sleeps.append(s)
        now["t"] += s

    fetcher = Fetcher(cache_dir=tmp_path / "c", min_gap_s=0.5, sleep=sleep,
                      clock=lambda: now["t"], opener=FakeOpener([("example.org", {})]))
    fetcher.get_json("https://example.org/a")
    fetcher.get_json("https://example.org/b")
    assert sleeps and sleeps[0] == pytest.approx(0.5)


# -- wikipedia.py ----------------------------------------------------------------


def test_queries_are_or_queries_in_the_right_language():
    queries = build_queries(["Taj Mahal Shah Jahan ne banwaya tha", "ताज महल शाह जहाँ ने बन्वया था"], "hi")
    assert queries[0][0] == "en" and " OR " in queries[0][1] and "ne" not in queries[0][1].split(" OR ")
    assert queries[1][0] == "hi" and "ताज" in queries[1][1]
    assert len(build_queries(["same words here", "same words here"], "en")) == 1


def test_wikipedia_candidates_are_lead_plus_a_clean_snippet(tmp_path):
    search = {"query": {"search": [{"title": "Narendra Modi",
                                    "snippet": 'was the <span class="searchmatch">chief</span> minister &amp; more'}]}}
    extracts = {"query": {"pages": {"1": {"title": "Narendra Modi", "extract": "Modi is an Indian politician."}}}}
    fetcher, opener, _ = make_fetcher(tmp_path, [("list=search", search), ("prop=extracts", extracts)])
    out = WikipediaLive(fetcher).search([("en", "modi OR gujarat")])
    assert len(out) == 1 and out[0].url == "https://en.wikipedia.org/wiki/Narendra_Modi"
    assert out[0].text == "Modi is an Indian politician. … was the chief minister & more"
    assert len(opener.calls) == 2                       # one search + ONE batched extract call


# -- factcheck.py ----------------------------------------------------------------

GOOGLE = {"claims": [{"text": "Pineapple juice is 500 times better than cough syrup",
                      "claimReview": [{"publisher": {"name": "Newsmeter", "site": "newsmeter.in"},
                                       "url": "https://newsmeter.in/pineapple", "title": "Is pineapple juice 500% better?",
                                       "textualRating": "False", "languageCode": "en"}]}]}


def test_the_key_is_read_from_the_environment_then_dotenv(tmp_path):
    assert load_key({"GOOGLE_FACTCHECK_API_KEY": " abc "}, tmp_path / "none") == "abc"
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nGOOGLE_FACTCHECK_API_KEY='from-file'\n", encoding="utf-8")
    assert load_key({}, env) == "from-file"
    env.write_text("GOOGLE_FACTCHECK_API_KEY=\n", encoding="utf-8")
    assert load_key({}, env) is None


def test_without_a_key_google_is_unavailable_and_makes_no_request(tmp_path):
    fetcher, opener, _ = make_fetcher(tmp_path, [("googleapis", GOOGLE)])
    client = GoogleFactCheck(fetcher, key="")
    assert client.available is False and client.search("anything") == [] and opener.calls == []


def test_google_reviews_are_parsed(tmp_path):
    fetcher, _, _ = make_fetcher(tmp_path, [("googleapis", GOOGLE)])
    hit = GoogleFactCheck(fetcher, key=KEY).search("pineapple")[0]
    assert (hit.publisher, hit.rating, hit.lang) == ("Newsmeter", "False", "en")
    assert hit.title == "Is pineapple juice 500% better?"


# -- pipeline/live.py ------------------------------------------------------------


def topic_encoder(texts):
    """A 3-dim 'topic' vector: alpha, beta, gamma word counts, normalised."""
    out = []
    for t in texts:
        v = [t.lower().count(w) for w in ("alpha", "beta", "gamma")]
        n = sum(x * x for x in v) ** 0.5
        out.append([x / n for x in v] if n else [0.0, 0.0, 0.0])
    return out


def evidence(tmp_path, *, wiki=None, google=None, key=KEY, tau=0.9):
    routes = [("list=search", wiki or {"query": {"search": []}}),
              ("prop=extracts", {"query": {"pages": {}}}), ("googleapis", google or {"claims": []})]
    fetcher, _, _ = make_fetcher(tmp_path, routes)
    return LiveEvidence(WikipediaLive(fetcher), GoogleFactCheck(fetcher, key=key),
                        encode=topic_encoder, tau_match=tau)


def review(claim, title, rating, url="https://fc.example/1"):
    return {"claims": [{"text": claim, "claimReview": [{
        "publisher": {"name": "FC"}, "url": url, "title": title,
        "textualRating": rating, "languageCode": "en"}]}]}


def test_a_review_of_this_very_claim_is_a_live_fast_path_match(tmp_path):
    live = evidence(tmp_path, google=review("alpha alpha beta", "alpha debunked", "False"))
    result = live.gather(["alpha alpha beta"], "en")
    assert result.match is not None and result.match.verdict == "Refuted"
    assert result.match.publisher == "FC" and result.match.score >= 0.9


def test_a_related_review_is_evidence_by_its_headline_not_its_claim_text(tmp_path):
    live = evidence(tmp_path, google=review("beta beta", "alpha headline", "False"))
    result = live.gather(["alpha beta gamma"], "en")
    assert result.match is None
    assert [p.text for p in result.passages if p.source == "factcheck_live"] == ["alpha headline — FC rating: False"]


def test_an_unmappable_rating_is_declined_never_guessed(tmp_path):
    live = evidence(tmp_path, google=review("alpha", "alpha headline", "Satire-ish nonsense"))
    assert live.gather(["alpha"], "en").match is None


def test_without_a_key_wikipedia_still_answers_and_the_trace_says_why(tmp_path):
    wiki = {"query": {"search": [{"title": "Alpha", "snippet": "alpha alpha"}]}}
    live = evidence(tmp_path, wiki=wiki, key="")
    result = live.gather(["alpha"], "en")
    assert any("no API key" in n for n in result.notes)
    assert result.passages and result.passages[0].source == "wikipedia"


def test_one_failing_source_does_not_take_the_other_down(tmp_path):
    routes = [("list=search", {"query": {"search": [{"title": "Alpha", "snippet": "alpha"}]}}),
              ("prop=extracts", {"query": {"pages": {}}}), ("googleapis", http_error(500))]
    fetcher, _, _ = make_fetcher(tmp_path, routes, retries=0)
    live = LiveEvidence(WikipediaLive(fetcher), GoogleFactCheck(fetcher, key=KEY), encode=topic_encoder)
    result = live.gather(["alpha"], "en")
    assert any("google fact check unavailable" in n for n in result.notes)
    assert [p.source for p in result.passages] == ["wikipedia"]
    assert KEY not in " ".join(result.notes)


def test_passages_come_back_most_relevant_first(tmp_path):
    wiki = {"query": {"search": [{"title": "Far", "snippet": "gamma"}, {"title": "Near", "snippet": "alpha alpha"}]}}
    result = evidence(tmp_path, wiki=wiki).gather(["alpha"], "en")
    assert result.passages[0].title == "Near"
    assert result.passages[0].cosine > result.passages[1].cosine


def test_an_encoder_failure_degrades_instead_of_raising(tmp_path):
    def broken(_):
        raise RuntimeError("no gpu")

    fetcher, _, _ = make_fetcher(
        tmp_path, [("list=search", {"query": {"search": [{"title": "Alpha", "snippet": "alpha"}]}}),
                   ("prop=extracts", {"query": {"pages": {}}}), ("googleapis", {"claims": []})])
    live = LiveEvidence(WikipediaLive(fetcher), GoogleFactCheck(fetcher, key=KEY), encode=broken)
    assert any("relevance scoring failed" in n for n in live.gather(["alpha"], "en").notes)
