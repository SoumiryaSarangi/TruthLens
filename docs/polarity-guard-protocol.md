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
