"""Lead extraction from MediaWiki dumps (`data/wikilead.py`), on hand-written
wikitext -- no dump needed."""

from __future__ import annotations

import io

from data.wikilead import (
    MIN_CHARS,
    article_url,
    cap,
    iter_pages,
    lead,
    lead_wikitext,
    strip_markup,
)


def test_lead_is_everything_before_the_first_heading():
    text = "Intro line.\n\n== History ==\nLater.\n=== Sub ===\nMore."
    assert lead_wikitext(text) == "Intro line.\n\n"


def test_nested_templates_and_infoboxes_are_removed():
    text = ("{{Infobox person\n| name = A\n| born = {{birth date|1950|1|1}}\n}}\n"
            "'''A''' is a minister.")
    assert strip_markup(text) == "A is a minister."


def test_links_keep_their_label_and_namespaced_links_are_dropped():
    text = ("[[File:x.jpg|thumb|Caption with [[inner link]]]]"
            "[[भारत|India]] and [[Delhi]] [[श्रेणी:राज्य]]")
    # The image caption -- including the link nested inside it -- is gone; an
    # article link keeps its label; a category in Hindi is dropped by its colon.
    assert strip_markup(text) == "India and Delhi"


def test_references_comments_and_tables_are_removed():
    text = ("Claim<ref name=a>{{cite web|url=http://x}}</ref> stays<ref name=b/>."
            "<!-- hidden -->\n{| class=wikitable\n|-\n| cell\n|}\nAfter.")
    assert strip_markup(text) == "Claim stays. After."


def test_external_links_keep_their_label_only():
    assert strip_markup("See [https://example.org the site] now.") == "See the site now."
    assert strip_markup("Bare https://example.org link.") == "Bare link."


def test_debris_from_an_unbalanced_template_is_dropped_not_kept():
    text = "{{Infobox\n| name = A\n| x = {{y}}\nProse survives."
    out = strip_markup(text)
    assert "Infobox" not in out and "|" not in out


def test_cap_cuts_at_a_devanagari_danda():
    text = "पहला वाक्य है। " * 200
    out = cap(text, 100)
    assert len(out) <= 100 and out.endswith("।")


def test_too_short_a_lead_is_dropped():
    assert lead("{{Disambig}}\nX may be:") == ""
    assert len(lead("Long enough. " * 10)) >= MIN_CHARS


DUMP = b"""<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <siteinfo><sitename>Wikipedia</sitename></siteinfo>
  <page><title>Delhi</title><ns>0</ns><id>5</id>
    <revision><id>1</id><text>'''Delhi''' is the capital of India.\n== History ==\nOld.</text></revision>
  </page>
  <page><title>Dilli</title><ns>0</ns><id>6</id><redirect title="Delhi"/>
    <revision><id>2</id><text>#REDIRECT [[Delhi]]</text></revision>
  </page>
  <page><title>Talk:Delhi</title><ns>1</ns><id>7</id>
    <revision><id>3</id><text>chat</text></revision>
  </page>
</mediawiki>"""


def test_iter_pages_reads_namespace_redirect_and_text():
    pages = list(iter_pages(io.BytesIO(DUMP)))
    assert [(p.page_id, p.title, p.namespace, p.redirect) for p in pages] == [
        ("5", "Delhi", 0, False), ("6", "Dilli", 0, True), ("7", "Talk:Delhi", 1, False)]
    assert lead_wikitext(pages[0].wikitext).strip() == "'''Delhi''' is the capital of India."


def test_article_url_is_percent_encoded():
    assert article_url("hi", "नई दिल्ली") == (
        "https://hi.wikipedia.org/wiki/%E0%A4%A8%E0%A4%88_"
        "%E0%A4%A6%E0%A4%BF%E0%A4%B2%E0%A5%8D%E0%A4%B2%E0%A5%80")
