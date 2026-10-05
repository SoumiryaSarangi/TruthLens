# "Why" on a fact-checked answer: reading the fact-check's opening paragraph (rule fixed before measurement)

**Status: written 2026-10-05, committed BEFORE any fact-check page is fetched by the new code.** Not changed afterwards except by dated corrections.

## What is added

When a message is answered from a published fact-check (the fast path: "newsmeter.in has already checked this message"), the card shows
a "Why" line: the opening paragraph of that fact-check article, quoted as the publisher wrote it, with the link. The owner asked for it
without a button, so it is fetched automatically on a fast-path hit (about 2% of messages).

**What leaves the machine:** one GET of the fact-checker's public article URL, which the card links to anyway. **No message text is sent.**
This is a change to the "offline unless the reader opts in" rule for the live path (SRS C-5, NFR-8), which was written about sending a
message's text to search engines: here nothing of the message is sent, the fetch has a 4-second timeout, is cached on disk, and failing
(no network, blocked, no usable paragraph) shows nothing and changes nothing else. `factcheck_lead: false` turns it off.

## Extraction (fixed here)

Stdlib only. From the page HTML: the `og:description` or `description` meta tag if it is a real sentence, else the first `<p>` of at least
60 characters outside navigation/footer/script text. Whitespace collapsed, HTML entities decoded, cut at a word boundary to 300 characters.
Rejected as boilerplate: text containing cookie, subscribe, sign in, newsletter, javascript, "all rights reserved"; text equal to or
contained in the page title.

## The measurement (before the feature is shown)

60 fact-checks drawn with seed 42 from the index (`data/interim/index/factcheck_meta.jsonl`), English, with a rating that maps to True
or False, stratified so no publisher supplies more than 6. Fetch each once with the code above.

**Success** = a lead of at least 60 characters survives the rejection rules. **The feature is shown to readers ONLY IF at least 70% of
the 60 succeed.** Otherwise it ships off (`factcheck_lead: false`), the code stays, and the numbers are reported. Ten extracted leads are
printed for reading; reading them cannot rescue a failure and does not change the rule.

## Honest limits

- A fact-check's opening paragraph is the publisher's own summary or the start of its article; it may not be the reason the claim is
  false. The card calls it "what the fact-check says", not "why".
- Sites change; a page that worked at measurement time may later fail, and then the line is simply absent.
- The index was built from fact-checks mostly dated before 2023; links may have moved.

## Dated corrections

(none to the rule.)

## Result (2026-10-05, run 39860deeb1d8, run once): FEATURE OFF

A lead was extracted for **36 of 60 = 60.0%** (bar 70%), so the "Why" line on a fact-check answer is **not shown** and the code is not wired
into the card. By publisher: nearly every AFP page (`factcheck.afp.com`, `factuel`, `fakty`, `checamos`, `semakanfakta`, ...) failed (the index files
non-English AFP desks under "en"), as did thip.media and some checkyourfact/newsmobile pages; boomlive, factly, politifact, factcheck.org, usatoday,
thequint and indiatoday mostly worked. Reading the 10 printed leads afterwards (cannot rescue the gate): most state **what the viral claim is**, not **why it
is false** ("A video showing police officers... has gone viral with a claim that..."), so even a success is often not an explanation. Not tuned.
A revised extractor (per-publisher rules, the verdict paragraph rather than the first one) would be a new protocol on a fresh sample.
