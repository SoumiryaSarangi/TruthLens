# Live retrieval v2: finding a page that is about the claim (APPROVED by the owner 2026-10-05; written before any code or run)

**Status: APPROVED (2026-10-05). The owner approved the three stages and supplied RC-E. Correction 1 below was written before RC-E or any v2 code was run.**

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

## Correction 1 (2026-10-05, before RC-E is run and before any v2 code exists): RC-E as received, and how the final bars use it
The owner supplied `real_forwards_new_100plus.csv` (copied to the git-ignored `data/private/real_forwards_new.csv`): 100 written claims, 50 F, 25 T, 25 U, each tied to a source URL (Income Tax, RBI, Jan Suraksha, PFRDA,
MoHUA, India Post, WHO, NHS, NASA, NCCIH, CDC and others), 32 distinct first URLs. Facts about the file, checked by script before any run:
- **All 100 are typed in Latin letters.** The language column says 21 are "Hindi (Devanagari)" and 5 "Gurmukhi Punjabi", but none contains Devanagari or Gurmukhi: the column is wrong for those 26 rows and **is not used**.
  RC-E tests English and Roman Hindi/Punjabi only. It cannot say anything about native script (RC-D, RC-B and A cover that).
- **15 U rows state their own hedge** ("... lekin evidence abhi limited hai", "... studies ka result abhi mixed hai", "... par evidence abhi settle nahi hua"), so the label can be read from the text. They are
  **dropped before any run (rows 86 to 100)**, the same policy as RC-D's six self-verdict rows. **85 claims remain: 50 F, 25 T, 10 U**, in 30 source families (a cluster is the first source URL). This is below the 100 asked for.
- Source column limits that do not change a label: row 78 (alpha-lipoic acid) cites the cinnamon page and row 88 (melatonin) cites a vitamin page; the labels stand. The month and "where seen" columns are unverified and unused.
  Many claims are variants of one source fact (five on RTGS, four on the e-rupee), so clusters, not rows, carry the statistics.
- Written claims, not collected forwards; labels are the owner's.

**RC-E is run on the CURRENT served system first (the v1 baseline), BEFORE any v2 code is started**, through the owner's running server, and its errors are NOT read (it is the fresh set; reading them would spend it).

**Final bars (replaces the A2-only wording above, because RC-E alone will have too few shown verdicts to carry a precision bar):** evaluated ONCE on the POOL of A2 (250) and RC-E (85), reported also per set. The pooled
bars: precision on shown decidable claims at least 0.85 with Wilson lower bound at least 0.80; false-Supported rate with Wilson upper bound at most 0.08; and a real gain: pooled shown decidable verdicts at least 30% above
the v1 baseline on the same pool (A2 28 plus RC-E's v1 count, measured first). Cluster-bootstrap intervals (RC-E by source URL) are reported and the more conservative of the row and cluster verdicts stands, as in
`docs/real-claims-protocol.md`. If the pooled bars fail, v2 is not shipped.

## Correction 2 (2026-10-05, after the Stage 1 code and tests exist, BEFORE any v2 retrieval number is computed): the retrieval check has a defined, non-zero baseline
The development check 1 above was written over claims that were silent under v1, so its v1 value is zero by construction and "a 25% relative rise" has no meaning. It is replaced by:
- **Population:** every gold-T/F claim of B (125) and of A1 (the English claims of AVeriTeC dev A1, gold T or F). Forms: the claim as run, plus the English translation stored in `diag_b.jsonl` for B (A1 is English already).
- **Measure:** the share of claims with at least one live Wikipedia page that passes the UNCHANGED relevance floor (BGE-M3 cosine 0.5) and the UNCHANGED `title_grounded` gate, under v1 queries and under v2 queries,
  from the live Wikipedia API (no fact-check calls, no NLI, no verdict; `scripts/retrieval_v2_check.py`, BGE-M3 on CPU so the owner's server is not disturbed). Also reported: Wikipedia requests per claim (mean and maximum).
- **Pass:** v2's share is at least 1.25 times v1's, on the pooled population and not lower on either set. If it fails, Stage 1 is dropped and recorded; nothing else in this protocol is run for it.
- **Deviation from the Stage 1 text, stated:** acronyms are all-capital tokens of 3 to 6 letters (2-letter forms such as "PM" are too ambiguous to search alone), up to 3 per claim, so a claim can cost up to 9
  Wikipedia calls (v1: 2 to 4), not 6. The request rate stays well inside the polite limit because the fetcher caches and spaces calls.

## v1 baseline on RC-E (2026-10-05, run `417fe19821a5`, `results/417fe19821a5.json`; the served system, before any v2 code was run on it)
RC-E, 85 claims (50 F, 25 T, 10 U): **0 verdicts shown (coverage 0.000)**, 0 false Supported in 50 false claims; precision is undefined with nothing shown. The errors of RC-E were not read (there are none to read). So the pooled A2 + RC-E
v1 baseline is **28 shown decidable verdicts, all correct** (A2 28, RC-E 0), and the gain bar fixed in correction 1 ("at least 30% above the v1 baseline on the same pool") is **at least 37 shown decidable verdicts on the pool**
(28 x 1.3 = 36.4, rounded up), together with precision at least 0.85 (Wilson lower bound at least 0.80) and a false-Supported Wilson upper bound of at most 0.08.

## Result of the Stage 1 development check (2026-10-05, run `b2a05007981d`, `results/b2a05007981d.json`): FAILED, Stage 1 is dropped
341 gold-T/F claims (B 125, A1 216), live Wikipedia, BGE-M3 on CPU, the unchanged relevance floor and title gate. Share of claims with at least one page that passes both:

| Set | n | v1 | v2 | ratio v2/v1 | v2 not lower than v1? |
| --- | --- | --- | --- | --- | --- |
| Pooled | 341 | 88 (0.258) | 81 (0.238) | 0.92 | no |
| B | 125 | 35 (0.280) | 37 (0.296) | 1.06 | yes |
| A1 | 216 | 53 (0.245) | 44 (0.204) | 0.83 | no |

The pass rule was a pooled ratio of at least 1.25 and no set lower. The pooled ratio is 0.92 and A1 is lower, so **v2 is not adopted and nothing further is run for Stage 1** (no full run, no A2, no restart). It also costs more:
1.91 Wikipedia requests per claim against 1.17 (maximum 5).
- **What this says:** deeper and more targeted queries did not find more pages that are about the claim; where v1 found a grounded page, v2 sometimes found a different top-5 and lost it (a plausible but UNTESTED reason: the added pages
  outrank the grounded one in the re-ranked top 5; not investigated, because a "v2b" tuned on these same dev claims would not be validatable). Only about a quarter of claims have a grounded Wikipedia page at all, with either
  query set, so the limit is the source, not the query. The code stays in the repo behind `live_retrieval_v2` (off, unwired, tests pass) as a recorded negative result.
- **Stage 2 is not run:** its condition (BOTH_NEI the largest remaining cause) is not met; NOT_JUDGED is.
- **Stage 3 (a new source) has a validity problem to settle first:** RC-E was written FROM agency pages (RBI, Income Tax, NCCIH, WHO and so on), so testing a source that adds those same sites on RC-E would be circular (the answer is in the
  page the claim was written from). A new source can only be validated on A2 and claims written independently of it.

## Stage 4 (2026-10-05, written BEFORE any fact-check match score is computed): the live fact-check match threshold, measured as a curve
**Why.** On AVeriTeC 55 of the 61 shown verdicts came from a published fact-check that matched the claim (cosine at least `TAU_MATCH` = 0.90, `pipeline/live.py`), not from Wikipedia. 0.90 was chosen on FEVER-style dev claims and was never measured as a
precision-versus-coverage curve on real claims, which `CLAUDE.md` requires for a fast-path threshold ("the tau table is the result"). A lower threshold would answer more claims from the fact-checkers' own verdicts, with the risk that the matched fact-check is
of a similar but different claim.

**Measurement (no verdict is served; the served system is not touched).** `scripts/factcheck_match_curve.py`: for every claim, the same Google Fact Check queries as the live path (every form of the claim, the English translation included), each hit
scored by BGE-M3 (CPU) against the fact-checked claim text exactly as `LiveEvidence.gather` does; the BEST hit that has a rating mapped to Supported or Refuted (`rating_to_verdict`) is stored (cosine, verdict, publisher, URL). Offline, for each
candidate tau in {0.90, 0.85, 0.80, 0.75, 0.70}, a claim is "shown by fact-check" when its best cosine is at least tau; as in the orchestrator, a fact-check match decides before Wikipedia is consulted, so the projected shown set is
{fact-check matches at tau} plus {claims the collected v1 run showed from Wikipedia with no match at tau}. Everything uses the stored per-claim results of `docs/real-claims-protocol.md`; no model other than BGE-M3 and no server is needed.

**Selection (dev sets: A1 plus B, gold T/F/U; fixed now).** The chosen tau is the LOWEST candidate that meets all of:
1. precision on shown decidable (gold T/F) claims, pooled, at least 0.90;
2. zero false-Supported (a shown Supported on a gold-F claim) in A1 plus B;
3. projected shown decidable verdicts at least 30% above the v1 count on A1 plus B (28 + 4 = 32 correct shown decidable verdicts; 32 x 1.3 = 41.6, so at least 42).
If no candidate meets all three, **Stage 4 is dropped and recorded**. Reported for every tau regardless: coverage, precision, false-Supported, shown on unverifiable (gold U) claims, and the share of shown verdicts per publisher.

**Final test (once).** The chosen tau, applied offline to the stored matches of A2 (250) and RC-E (85), pooled, against the bars of correction 1: precision at least 0.85 with Wilson lower bound at least 0.80; false-Supported Wilson upper bound
at most 0.08; and pooled shown decidable verdicts at least 37 (the baseline 28 plus 30%); the more conservative of row and source-cluster verdicts stands. Fact-check matching does not read the agency pages RC-E was written from, so RC-E is a fair
test here (unlike a new Wikipedia-side source). A2's matches are computed only after the dev choice is recorded. **If it passes, `TAU_MATCH` for the live path is changed (a separate config key `tau_live_match`), the owner restarts the server, and
A2 plus RC-E are run through the served system once to confirm the offline projection; if the served run disagrees with the projection, the worse reading is reported.** If it fails, nothing is shipped.
