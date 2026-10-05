"""Extraction of a fact-check's opening paragraph (docs/factcheck-lead-protocol.md). No network."""
from __future__ import annotations

from retrieval.live.factcheck_lead import MAX_CHARS, extract_lead, fetch_lead

PAGE = """<html><head><title>Is pineapple juice 500% more effective than cough syrup?</title>
<meta property="og:description" content="A viral message claims pineapple juice beats cough syrup by 500 times. Doctors say no such study exists."></head>
<body><nav><p>Home | About us and a very long navigation line that is not an article paragraph at all</p></nav>
<article><p>Short.</p><p>The claim was shared widely on WhatsApp in early 2020 and attributed to a research group that does not exist.</p></article>
<footer><p>All rights reserved. Subscribe to our newsletter for more fact checks every single day of the week.</p></footer></body></html>"""


def test_the_meta_description_is_preferred_when_it_is_a_real_sentence():
    lead = extract_lead(PAGE)
    assert lead.startswith("A viral message claims pineapple juice")


def test_without_a_meta_description_the_first_real_article_paragraph_is_used_and_navigation_and_footer_are_not():
    page = PAGE.replace('<meta property="og:description" content="A viral message claims pineapple juice beats cough syrup by 500 times. Doctors say no such study exists.">', "")
    lead = extract_lead(page)
    assert lead.startswith("The claim was shared widely on WhatsApp")
    assert "newsletter" not in lead and "navigation" not in lead


def test_boilerplate_and_a_repeated_title_are_rejected():
    page = "<html><head><title>Fake news about lemons</title><meta name='description' content='Fake news about lemons'></head><body><p>We use cookies to improve your experience on this website and for analytics.</p></body></html>"
    assert extract_lead(page) is None


def test_a_long_lead_is_cut_at_a_word_boundary():
    page = "<html><body><p>" + "word " * 200 + "</p></body></html>"
    lead = extract_lead(page)
    assert len(lead) <= MAX_CHARS + 1 and lead.endswith("…")


def test_garbage_and_non_http_urls_give_nothing(tmp_path):
    assert extract_lead("<<<not html") is None
    assert fetch_lead("file:///etc/passwd", cache_dir=tmp_path) is None
    assert fetch_lead("", cache_dir=tmp_path) is None


def test_a_cached_answer_is_returned_without_the_network(tmp_path):
    import hashlib
    import json

    url = "https://example.org/fact-check/x"
    (tmp_path / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".json")).write_text(json.dumps({"url": url, "lead": "Cached lead sentence that is long enough to be used as a lead."}))
    assert fetch_lead(url, cache_dir=tmp_path).startswith("Cached lead")
