# A polarity guard for live fact-check matches (DRAFT, awaiting the owner's approval; written 2026-10-05 before any code or data for it exists)

**Status: DRAFT. Nothing here is built or run. The owner approves it, it is committed as final, then the test set is built and the code written.**

## Why
`docs/live-retrieval-v2-protocol.md` (Stage 4) lowered the live fact-check match threshold from 0.90 to 0.70 and it was confirmed on the served system (run `f0d7ab316ff0`). Its recorded limit: **a similarity match carries no polarity.** A claim
is matched to a published fact-check by how close the two sentences are, and a sentence and its negation are close. Seen once in the data (owner's claims): the TRUE claim "NASA says the Great Wall of China is not visible to the naked eye from the Moon"
matched (cosine 0.77) a Snopes fact-check of the opposite claim and was shown Refuted. The harmful direction (a false claim inheriting "Supported" from a fact-check of a true claim) did not occur in 205 false claims, but nothing tested for it
on purpose. This protocol tests for it on purpose, and adds a guard only if the guard earns its place.

## The guard (one rule, fixed now; no second variant is tried on the same data)
When a live Google fact-check hit would decide a claim, the English form of the claim and the English text of the matched fact-checked claim are read by the live NLI model that is already loaded (DeBERTa-v3-large, `LIVE_NLI_MODEL`):
premise = the fact-checked claim text, hypothesis = the user's claim (English form). **The match is BLOCKED if the model's probability of Contradiction is at least 0.5**; a blocked match falls through exactly as if no fact-check had matched
(the Wikipedia route, or no verdict). Entailment and Neutral both let the match stand: Neutral is the "similar but different claim" case, which this guard does not claim to fix.
- **It can only remove verdicts, never add one.** So it cannot create a false Supported; the question is only how many wrong verdicts it removes against how many right ones.
- It applies at every cosine (a negation can sit above 0.90 too). It applies only when the matched claim text is English (the NLI model reads English); matches in another language are not checked, and their share is reported as a limit.
- No threshold is tuned: 0.5 is the model's own decision boundary and is fixed here. The match threshold 0.70 and everything else stay as served.

## The test set RC-F (built by the owner from real fact-checks; written and labelled BEFORE any guard output exists)
Dev sets A1 and B (and A2, RC-E) contain too few wrong matches to say anything (3 wrong in 53 shown on A1; 1 in B). So the guard is tested on claims built to contain the case.
1. **Sources (supplied by the agent):** about 60 real claims with a clear rating from a published fact-check, taken from the Google Fact Check index (Alt News, BOOM, Vishvas News, AFP, Snopes, PolitiFact and similar), each with publisher, rating and URL
   (`data/private/rcf_sources.csv`, git-ignored). Only simple factual claims with a rating that maps cleanly: False, Fake, Pants on Fire, Misleading-as-false count as F; True, Correct, Accurate count as T; Mixture, Partly false, Unproven, Satire
   are dropped. Mostly F, because that is what fact-checkers publish; at least 8 T.
2. **For each source the owner (or friends) writes two claims** in their own WhatsApp style, English or Roman Hindi/Punjabi mixed: **(a) a paraphrase** that says the SAME thing in other words (gold = the source's rating), and **(b) a negation** that says the
   opposite (gold = the opposite of the source's rating: the negation of a False-rated claim is TRUE, the negation of a True-rated claim is FALSE). A pair the owner cannot write naturally is skipped and counted. Aim: at least 100 rows (50 pairs).
3. Rows carry the source id, so a pair is a cluster for the statistics. The paraphrases are the "must still answer" arm; the negations are the "must not be answered the wrong way" arm. They are written claims, labelled by the owner.

## Measurement (no served change; BGE-M3 and DeBERTa on CPU so the owner's server is not disturbed)
For every RC-F row, the same Google queries as the live path are made, the best matched hit at tau 0.70 is taken as served, and the guard is applied offline by running the NLI model on (matched claim text, user claim). Reported for the paraphrases and
the negations, separately, WITHOUT and WITH the guard: shown verdicts, correct, wrong (a shown verdict that contradicts the gold), and for gold-F rows shown Supported. The same is computed on A1 and B (dev, already read) and on A2 and RC-E from the stored
matches as a retention check only (they are spent for selection and are not used to choose anything).

## The pass rule (fixed now)
The guard is adopted only if ALL hold:
1. **It removes the wrong ones:** on the RC-F negations, wrong shown verdicts WITH the guard are at most 25% of those WITHOUT it. The test is only informative if there are **at least 6 wrong shown negations without the guard**; with fewer, the result is
   "not testable on this set" and the guard is NOT adopted (an untested guard is not shipped).
2. **It keeps the right ones:** at least 85% of the correct shown verdicts on the RC-F paraphrases survive, and at least 90% of the correct shown verdicts on A1, B, A2 and RC-E (pooled) survive.
3. **It never makes it worse:** no new wrong shown verdict appears with the guard on any set (by construction impossible; checked anyway).
4. False Supported on RC-F with the guard is zero.
Cluster-bootstrap intervals (a cluster is a source id) are reported next to every rate, and where the row verdict and the cluster verdict disagree the more conservative stands.

**If it passes:** the guard is wired into the live match behind a config key `live_match_guard` (off by default), unit-tested with fake models, the owner restarts the server, and RC-F is run through the served system once to confirm the offline result. If the
served run disagrees, the worse reading is reported and the key is left off. **If it fails, nothing ships, the failure is reported with the same weight, and the limit stays disclosed.**

## Limits stated now
- The guard only handles polarity. A similar-but-different claim (a different number, place or date) is Neutral to the model and is NOT blocked; that error class stays disclosed.
- It reads English only; matches to fact-checks written in other languages are not checked.
- RC-F contains the negations the owner can write naturally; adversarial or subtle negation (quantifiers, scope, "only") is not covered.
- Sources come from the Google index the live path uses, so RC-F says nothing about topics fact-checkers did not cover.

## What the owner provides
After approval the agent builds `rcf_sources.csv` (about 60 real fact-checked claims, with publisher, rating and URL) and sends it. The owner (or friends) writes a paraphrase and a negation for each, in the same column layout as
`real_forwards.csv` plus a `source_id` and a `kind` column (paraphrase or negation), without looking at any system output. About 100 sentences.

## Status and correction 1 (2026-10-05, after approval; written BEFORE any RC-F sentence exists and before any guard output)
**The owner approved the protocol.** The source list was built from the Google Fact Check index by `scripts/build_rcf_sources.py` (English claims, 6 to 22 words, clear rating, no video/photo/post claims, no politics or bare statistics, at most 5 per publisher),
then curated by hand for simple factual claims whose paraphrase and negation can be written naturally (near-duplicate lemon claims, question headlines about events, "mostly false" ratings and person-specific political items were dropped). Result:
**44 sources: 40 rated False and only 4 rated True.** The protocol asked for at least 60 and at least 8 True. The index simply holds very few True-rated claims (fact-checkers publish mostly debunks): 8 True candidates across about 250 queries, 4 usable.
Consequences, stated now:
- **The harmful direction (a false claim inheriting "Supported") can be tested on at most 4 sources**, so it is effectively NOT tested; it stays a disclosed limit and pass-rule item 4 is reported but cannot carry weight.
- **The observable error is the mild direction:** the negation of a False-rated source is a TRUE claim, and a polarity-blind match shows it Refuted. The test of pass-rule item 1 uses those negations (40 sources).
- The informativeness condition is unchanged: with fewer than 6 wrong shown negations WITHOUT the guard the result is "not testable" and the guard is not adopted.
- The owner fills a wide sheet (`rcf_for_owner.csv`: one row per source, columns `paraphrase`, `negation`, `language`, `skip_reason`); the agent converts it mechanically to long form (kind = paraphrase or negation; gold of a paraphrase = the source's rating,
  gold of a negation = the opposite). Rows with a blank cell are skipped and counted.

## Correction 2 (2026-10-05; RC-F received; written BEFORE any RC-F sentence is run and before any guard output exists)
**RC-F as received:** `rcf_for_owner_filled.csv` (git-ignored in `data/private/`), 44 sources, every row filled, none skipped; converted mechanically (`data/private/rcf_claims.csv`) to **88 sentences: 44 paraphrases (40 gold F, 4 gold T) and 44 negations
(40 gold T, 4 gold F)**; 48 Roman Hindi and 40 English; 6 of the "paraphrases" are verbatim copies of the source sentence (reported separately, and not removed). Written by the owner without sight of any system output.

**How the offline measure is computed (fixed now):**
- **Without the guard** = what the running server (tau_live_match 0.70, no guard) returns for the sentence (`diagnose --set f` stores the result, the English translation and whether a fact-check match decided).
- **With the guard** = the same result, except that when a FACT-CHECK match decided and the guard blocks it (P(Contradiction) of DeBERTa, premise = the matched fact-checked claim text, hypothesis = the sentence's English form, at least 0.5; matched text in English only),
  the sentence is counted as **silent**. The true served fall-through (a blocked match may be answered by Wikipedia instead) is not simulated; that is what the served confirmation run measures. A result decided by Wikipedia is never changed by the guard.
- The matched hit is recomputed with the same Google queries and BGE-M3 scoring as the live path (`best_match` in `scripts/factcheck_match_curve.py`, now also returning the hit's claim text and language), on the English form where one exists.
- **Retention on the natural sets** uses the projection at 0.70 of A1, B, A2 and RC-E (`factcheck_match_curve.project`): of the correct shown verdicts decided by a fact-check match, the share the guard does not block. Their errors are not used to choose anything.
- Outcomes per RC-F kind: shown, correct, wrong (a shown verdict that contradicts the gold; for a gold-F sentence, shown Supported is also counted as false Supported). The pass rule above is applied to these numbers exactly as written. Row and source-cluster bootstrap intervals (1000 resamples, seed 42) are reported.

## Result (2026-10-06, run `2bbc13d6e982`, `results/2bbc13d6e982.json`): the guard is NOT adopted by the pre-registered rule (5 of 6 conditions hold; item 4 fails)
Run once, offline (DeBERTa-v3-large and BGE-M3 on the GPU after the owner stopped the server, because the models together do not fit in the RAM left beside the running server), on the owner's 88 sentences and the natural sets' stored matches.

| RC-F | sentences | shown (served, no guard) | correct | wrong | shown with the guard | wrong with the guard |
| --- | --- | --- | --- | --- | --- | --- |
| paraphrases (same claim, other words) | 44 | 28 | **28** | 0 | 28 | 0 |
| negations (the opposite claim) | 44 | 18 | **0** | **18** | 4 | 4 |

- **The headline finding is about the system as served, not the guard: every verdict shown on a negated claim was wrong (18 of 18).** A polarity-blind match answers "X does not cure Y" with the verdict of "X cures Y". Where the system speaks at all it does so for the claim
  it matched, whatever the sentence says. 14 of those 18 were decided by a live Google fact-check match and the guard blocked all 14 (P(Contradiction) 0.65 to 0.9996); the 4 left were not live matches at all (below).
- **Rules, as fixed:** informative (18 wrong negations without the guard, at least 6): yes. 1, wrong negations with the guard at most 25% of those without: **4 of 18 = 22%** (cluster bootstrap 95% interval 5% to 43%): met. 2a, right paraphrases kept at least 85%: **28 of 28**: met (also
  22 of 22 when the 6 verbatim copies are excluded). 2b, right natural-set fact-check verdicts kept at least 90%: **111 of 112 = 99%**: met (the guard blocked 3 of 117: one right, two wrong; the A1, B, A2 wrong ones fell from 5 to 3). 3, no new wrong verdict: met.
  **4, zero false Supported on RC-F with the guard: NOT met** (1 false Supported, unchanged by the guard).
- **Why item 4 fails:** the 4 wrong negations that remain, including the one false Supported (the negation of the True-rated Kobe Bryant claim, "Kobe was not the only person to ..."), were decided by the OFFLINE fast path (`path == "fast"`, the stored fact-check index at tau 0.90), not by a live Google match. 12 sentences in RC-F were fast-path decided with no live
  match to check. **The guard as specified covers live matches only, so it cannot touch them.** The offline fast path is polarity-blind in the same way.
- **Decision:** by the rule ("adopted only if ALL hold") the guard is **not adopted**, and it is not re-interpreted after the fact (correction 1 had said item 4 "cannot carry weight", which is not the same as waiving it). Nothing in the served configuration changes. The result is nonetheless clear about what a fix would need:
  **a guard on BOTH matching paths** (the offline fast path matches a fact-check title/claim in the stored index; the same NLI check would apply to it). That is a new rule on a new component and needs its own protocol and FRESH sentences: RC-F has now been read and cannot validate a changed guard.
- **Limits:** RC-F has only 4 True-rated sources, so the harmful direction rests on one case; the guard reads English only (1 live match in another language was unchecked); a blocked match is counted silent here, and the true served fall-through to Wikipedia was not measured.

## Correction 3 (2026-10-06): the explanation of why item 4 failed was wrong; the numbers and the decision are unchanged
The Result section above says the 4 remaining wrong negations "were decided by the OFFLINE fast path". **That was not checked and is false.** Checked afterwards: the offline fast path (`matching: factcheck`, tau 0.90) fires on only 1 of the 88 RC-F sentences (a correct Flipkart paraphrase, cosine 0.933).
The 12 sentences that the offline recomputation found no match for were all Roman Hindi sentences answered through **live Google fact-checks** (`live_sources` contain `google_factcheck`; path `fast` is also what a live match returns). My offline check built its queries from the sentence and its English
translation only; the live path also queries a **transliterated Devanagari form** of a Roman Hindi sentence, which returns Hindi-language fact-checks that the English-only guard cannot read. So the real blind spot of the guard as specified is **a matched fact-check written in a language other than English**, not the
offline path. Rule item 4 still fails as stated and the guard is still not adopted. The next design must (1) translate a non-English matched claim to English before the NLI check, and (2) be measured through the SERVED pipeline, not an offline re-creation, so the forms, the matches and the fall-through are exactly the served ones.
