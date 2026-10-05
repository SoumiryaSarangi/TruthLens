# "Why" on a fact-checked answer, take 2: the sentence that states the finding (rule fixed before measurement)

**Status: written 2026-10-05, committed BEFORE the extractor in this protocol has been run on any page.** Not changed afterwards except by
dated corrections. It follows `docs/factcheck-lead-protocol.md`, whose result was OFF (36 of 60 = 60% against 70%) and whose leads
mostly restated the claim ("A post claiming that pineapple is more effective than cough syrups is doing the rounds") instead of saying why it is
false. That result stands; this is a different extractor on a fresh sample, asked for by the owner ("Pineapple still doesn't have a why").

## The extractor (fixed here)

Same fetch as before (one GET of the public article URL, 4 s timeout, no message text sent, cached, any failure means nothing is shown).
From the article's paragraphs (outside nav/footer/script, first 25 paragraphs), split into sentences and take the **first sentence of 40
to 300 characters that contains a conclusion cue** and is not boilerplate and not contained in the page title:

`found that`, `no evidence`, `not true`, `false`, `fake`, `misleading`, `doctored`, `edited`, `fabricated`, `baseless`, `hoax`, `debunk`,
`there is no`, `has no`, `have no`, `does not`, `did not`, `is not`, `was not`, `not a`, `not an`, `actually`, `in fact`, `old video`,
`old image`, `unrelated`, `satire`, `no such`, `untrue`, `incorrect`, `unverified`, `not found`, `no record`, `clarified`, `denied`.

If no such sentence exists, nothing is shown (the card says nothing extra). The card labels it "What the fact-check says", never "why".

## The measurement

A FRESH sample: 60 fact-checks from `data/interim/index/factcheck_meta.jsonl`, English, rating True or False, seed 43, at most 6 per
publisher, **disjoint from the 60 of the first protocol (run 39860deeb1d8)**. Two gates, both must hold for the feature to ship:

1. **Coverage:** a finding sentence is extracted for **at least 70%** of the 60.
2. **It states a finding:** of the extracted sentences, **at least 70% state a finding about the claim** (it is false, misleading, unsupported, old,
   edited, unrelated) and not merely what the claim says or a procedural remark. **I (the assistant) label each extracted sentence yes/no** against this
   rubric BEFORE looking at whether that changes the verdict on the gate, and every sentence with my label is written to the result file so the
   owner can audit it; the labelling is mine and so is subjective, which is why the bar is stated in advance and the sentences are published.

If either gate fails, the feature ships OFF (`factcheck_lead: false`), the numbers are reported, and a further change is a new protocol on a fresh sample.

## How it is shown if it passes

Fast-path (matched fact-check) cards only, automatically, no button: under the fact-check headline, "What the fact-check says: “…”" with a
link. Absent when extraction fails. `factcheck_lead: true` in the served config turns it on; false turns it off.

## Honest limits

- One sentence from an article is not an explanation of the whole finding, and a cue word can appear in a sentence that is not the finding.
- The sample is of the index, not of the fact-checks that real forwards will hit; AFP desks and some publishers failed last time and probably will again.
- My labelling is subjective and unblinded.

## Dated corrections

(none to the rule.)

## Result (2026-10-05, run 9e209d11fc4d, run once): FEATURE OFF

**Gate 1 failed: a finding sentence was extracted for 27 of 60 = 45.0%** (bar 70%), so the feature is off and gate 2 (my labelling) was not run.
Works: thequint 4/4, usatoday 6/6, factly 4/4, newsmobile 4/6, newsmeter 2/2 (the pineapple fact-check's publisher), politifact, factcheck.org, altnews.
Fails: boomlive 0/4, checkyourfact 0/6, indiatoday 0/3, asianet 0/2, thip.media 0/1 and every AFP desk (0/12) - these pages mostly give no usable
paragraph to a plain GET (client-rendered). Of the first 8 extracted sentences, 2 were junk by eye (a PolitiFact Facebook-programme sentence; a "Follow us on
Facebook! ... latest debunks" footer), read after the run and not a gate. Not tuned. Per-publisher rules or a headless browser would be a new protocol and
a new dependency.
