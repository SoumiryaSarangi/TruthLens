# Live retrieval v2: finding a page that is about the claim (DRAFT, awaiting the owner's approval; written 2026-10-05 before any code or run)

**Status: DRAFT. Nothing in this file is built or run. The owner approves it, then it is committed as final, then code is written.**

## Why
`docs/silence-diagnosis-protocol.md` (run `2e34a941d690`): the served live check is silent on 96% of the owner's written claims and 88% of AVeriTeC dev claims. In 64% to 73% of silent cases pages were
found but none was about the claim's subject; in a further 26% to 30% a page was judged but nothing in the two nearest sentences settled it. Three causes in the code, all read from the repo:
1. **One query per claim:** `build_queries` (src/retrieval/live/wikipedia.py) sorts the content words ALPHABETICALLY, keeps 8, and joins them with OR. Wikipedia's ranking over eight unrelated ORed words favours pages that
   happen to contain many of them ("Intermittent water supply" for a UPI claim).
2. **Shallow:** only the top 5 titles of that one query are fetched.
3. **Acronyms and short forms are invisible:** "UPI", "OTP", "PMJDY", "LPG", "EPFO" never reach "Unified Payments Interface", "One-time password" and so on; the title gate then rejects the page that
   was found. (Post-hoc simulation: acronym matching alone would have admitted 23 of 125 decidable B claims.)

The goal is the largest coverage gain that keeps the bars below. **Safety comes first: nothing here loosens the title-grounding gate, the two-model agreement (V2), the relevance floor or any threshold.**

## Frozen (must not change in any stage)
The live rule V2 (two NLI models must agree, English route), the grounding gate `title_grounded`, `LIVE_RELEVANCE_FLOOR` 0.5, the fast-path thresholds, the offline path, the test split, A2 until the final test.

## Stage 1: better queries and depth (Wikipedia only, no new model, no GPU)
Candidate retrieval is widened; judgement is untouched. For each claim, using the English form (and the original form as today):
- **Q0:** the current OR query (kept, so nothing that worked is lost).
- **Q1: entity query.** The claim's proper-noun phrases (runs of capitalised words), numbers/years, and acronyms, joined as an AND of quoted phrases; if it returns nothing, the same as OR.
- **Q2: acronym resolution.** Every all-capital token of 2 to 6 letters (and the claim's quoted phrases) is searched ALONE on English Wikipedia; its top 2 titles are added to the candidate pool. No dictionary is
  written by hand: the resolution comes from Wikipedia, so it cannot be fitted to the dev claims.
- **Depth:** top 8 titles per query instead of 5. The union is re-ranked by BGE-M3 exactly as today and the top 5 Wikipedia passages go on, as today.
- The extra calls are made in one batch per language, and the total stays at most 6 Wikipedia requests per claim (rate limit).

## Stage 2: read more of a good page (only if Stage 1 is adopted or fails for lack of effect)
For BOTH_NEI cases the premise is the two sentences nearest the claim. Candidate: the premise is the three nearest sentences from the lead plus the matched snippet, with the SAME two-model agreement and the same
bars. Whole-article reading is NOT in scope here: it multiplies spurious "Refutes" and would need its own protocol. Stage 2 is only run if Stage 1's result leaves BOTH_NEI the largest remaining cause.

## Stage 3: a new source (government and agency fact-checks), decided AFTER Stage 1
Only if Stage 1 leaves NO_SOURCE or NOT_JUDGED large because the page does not exist on Wikipedia. Candidate: the PIB Fact Check feed and the RBI/UIDAI/EPFO advisory pages, read as headlines like the Google
fact-check results are (the publisher's own rating, never a model's reading). Needs its own robots/terms check and its own protocol amendment; not designed in detail now.

## How each stage is judged
**Development stage (A1 plus B are the dev sets; they have already been read, so they can choose, not validate).**
1. **Retrieval check, no verdict:** among the 114 gold-T/F claims that were silent with a relevant page (the diag files), the share that has at least one page that passes the UNCHANGED title gate, v1 vs v2.
   Pass: v2 raises it by at least 25% relative. Fail: the stage is dropped and recorded.
2. **Full run:** the unchanged pipeline with v2 retrieval, A1 (250) and B (150) through the owner's server after a restart, same collector. Pass: shown decidable verdicts rise by at least 30% relative over the
   baseline (A1 28, B 6), with precision at least 0.85 and zero new false-Supported on gold-F claims in A1+B. A false Supported on a dev claim is read and its cause recorded before anything else.

**Final test (once, locked).**
- **A2** (250, never read) AND **a new set RC-E** supplied by the owner (see below), run ONCE with the final combination. Bars (the same as `docs/real-claims-protocol.md`): precision on shown decidable
  claims at least 0.85 with Wilson lower bound at least 0.80; false-Supported rate with Wilson upper bound at most 0.08; and an actual gain: shown decidable verdicts on A2 at least 34 (baseline 28; this is the
  count that 31 shown verdicts moves to by 30%), reported with its interval. RC-B/D language consistency is reported beside it.
- **If the bars fail, v2 is NOT shipped**, the failure is reported with the same prominence, and the served system stays as it is.
- The conservative rule of the earlier protocol applies: when two sets disagree, the worse verdict is the headline.

## What the owner provides (RC-E)
At least 100 NEW written claims (more is better), none of them from the 150 already used, with the same columns as `real_forwards.csv` (id, text, language, label T/F/U, source_for_label), written and labelled
BEFORE anyone sees any v2 output. Mix: about half false scam or health forwards, a quarter true, a quarter that no public source settles (U). Each claim tied to a source that actually settles it (a PIB, RBI, WHO,
Wikipedia or fact-check page). They are written claims, and are reported that way.

## Limits stated now
Wikipedia will still not hold pages for many local forwards; Stage 1 cannot create coverage that does not exist, only find coverage that is there. The expected gain is modest (the post-hoc ceiling from the title
gate alone was about 18% of decidable B claims), and the true effect may be smaller or none. A negative result is reported as such. Fast-path Roman matching and offline-wording changes are separate protocols.
