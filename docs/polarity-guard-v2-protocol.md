# Polarity guard v2: translate the matched fact-check, then check it; measured through the served pipeline (APPROVED by the owner 2026-10-06; written before any v2 code or RC-G sentence exists)

## Why
`docs/polarity-guard-protocol.md` (run `2bbc13d6e982`, corrections 1 to 3): on 44 negated versions of real fact-checked claims the served system showed 18 verdicts and **all 18 were wrong** (a negated claim inherits the verdict of the claim it denies); on 44
same-polarity paraphrases it was right on all 28 it answered. An English-only NLI guard on live Google matches blocked 14 of the 18 and kept every right paraphrase, but failed its pre-registered item 4 because the 4 wrong negations left were Roman Hindi sentences matched to
**Hindi-language** fact-checks that an English-only check cannot read. RC-F is spent for any changed guard. This protocol fixes the changed guard and a fresh test BEFORE either is built.

## The guard G2 (one rule, fixed now; no second variant is tried on the same data)
When a published fact-check match would decide a claim (a live Google match, or the offline fast-path match at `tau_match`), the claim's English form is checked against the matched fact-checked CLAIM text:
1. **Matched text in English:** used as is. **In Hindi or Punjabi:** translated to English with the translator the live path already loads (NLLB, `hi`/`pa` to `en`). **In any other language:** not checked; the match stands and the trace says "match not checked (language)".
2. **The check:** the live NLI model already loaded for the live verdict (DeBERTa-v3-large, `LIVE_NLI_MODEL`), premise = the (translated) matched claim text, hypothesis = the English form of the user's claim. **If P(Contradiction) is at least 0.5 the match is BLOCKED** and the claim falls through to the evidence path exactly as if
   no fact-check had matched (Wikipedia, or no verdict). Entailment and Neutral let the match stand.
3. It applies at every cosine, on both matching paths, and **can only remove a fact-check verdict**; a fall-through can still produce a Wikipedia verdict (the validated two-model rule), which is why the "no new wrong verdict" condition below exists.
4. Behind a config key `live_match_guard` (off by default, absent from `describe()` unless on), unit-tested with fake models. The threshold 0.5 and every other served setting are untouched.

## Test set RC-G (fresh, written by the owner BEFORE any v2 output; none of RC-F's 44 sources)
Built like RC-F (`scripts/build_rcg_sources.py`, different queries, RC-F claims excluded, curated by hand for simple factual claims): **39 sources, 31 rated False and 8 rated True** (more True-rated claims than RC-F, so the harmful direction rests on 8 sources, not 4).
For each source the owner writes **a paraphrase** (gold = the source's rating) and **a negation** (gold = the opposite), in WhatsApp style, English or Roman Hindi, without looking at any system output. A pair that cannot be written naturally is skipped and counted.
Expected about 78 sentences, one cluster per source. Written claims, owner-labelled.

## Measurement: through the SERVED pipeline, twice
The offline re-creation of RC-F missed the transliterated forms the live path queries, so v2 is measured on the real thing. **Arm A:** the server as it stands (no guard), RC-G sent through `POST /verify` with `live_search: true`. **Arm B:** the server restarted with `live_match_guard: true`, the same sentences again, and A2 plus RC-E
(the retention check against the recorded served run `f0d7ab316ff0`). The owner restarts the server between arms. Sequential, one retry if a source is degraded; degraded runs are counted. Per sentence the collector stores the verdict, whether a match decided, the English form, the trace notes (guard blocked / not checked).

## The pass rule (fixed now)
G2 stays on (is adopted) only if ALL hold:
1. **Informative:** arm A shows at least 6 wrong negations. With fewer the result is "not testable" and the guard is not adopted.
2. **It removes the wrong ones:** arm B's wrong shown negations are at most 25% of arm A's.
3. **It keeps the right paraphrases:** at least 85% of arm A's correct shown paraphrases are still shown correctly in arm B.
4. **It keeps the right natural answers:** on A2 plus RC-E, arm B's correct shown decidable verdicts are at least 90% of the recorded 51 (run `f0d7ab316ff0`).
5. **No new wrong verdict:** every wrong shown verdict in arm B (any set) was already a wrong shown verdict in arm A, or is reported by name and counts against adoption.
6. **No false Supported on RC-G in arm B** (the harmful direction; 8 True-rated sources).
Cluster-bootstrap intervals (a cluster is a source) are reported beside the rates, and the unchecked rate (fact-check-decided answers whose matched text was in an unchecked language) is reported. If any item fails, `live_match_guard` stays off, nothing ships, and the failure is reported with the same weight.

## Limits stated now
Hindi and Punjabi matched texts depend on NLLB's translation; other-language fact-checks are unchecked; the guard handles polarity, not a different number, place or date; RC-G covers topics fact-checkers published and Roman Hindi/English only; only 8 True-rated sources.

## Correction 1 (2026-10-06; RC-G received; written BEFORE any RC-G sentence is run)
**RC-G as received:** `rcg_for_owner_filled.csv` (git-ignored in `data/private/`), 39 sources, every row filled, none skipped, none a verbatim copy; converted mechanically (`data/private/rcg_claims.csv`) to **78 sentences: 39 paraphrases and 39 negations**; all typed in Latin
letters (the language column says English for many Roman Hindi sentences and is not used). Written without sight of any system output.
**One labelling defect of the SOURCE LIST, found by reading the sources before any run:** source 33 is the fact-checker's debunk headline "Fact Check: Indian Railways Has Not Restored Senior Citizen Concessions on Train Ticket Fares", whose rating False applies to the claim it debunks
(that the concessions were restored). The owner's paraphrase restates the headline, which is TRUE; the mechanical rule (paraphrase gold = the source's rating) would label it False. **For this one pair the gold is flipped (paraphrase T, negation F)**, a labelling fix made before any run and independent of any output.
Result: **paraphrases 30 gold F and 9 gold T; negations 30 gold T and 9 gold F** (the flipped pair adds a ninth source for the harmful direction: 9 negations are gold F). Sources 29, 32 and 34 also contain a negative word but are themselves the false claims, so their mapping is unchanged.
**Run procedure and files:** `diagnose --set g --suffix _A` (guard off) and `--suffix _B` (guard on) write `diag_g_A.jsonl` and `diag_g_B.jsonl`; the retention arm is `collect --set a --only A2 --suffix _guard` and `collect --set e --suffix _guard`; `scripts/polarity_guard_v2_check.py` computes the rule once.

## Result (2026-10-06, run `b3a6fdfb6933`, `results/b3a6fdfb6933.json`): the guard FAILS its pre-registered rule on two items, both narrowly; `live_match_guard` is set back to false
Both arms through the served pipeline (arm A: git `62165de`, guard off; arm B: git `7488e0a`, guard on, the owner restarted between arms), RC-G (78 sentences) and A2 plus RC-E (335 claims, the retention check). A first computation counted verdicts on unverifiable (gold U) claims as right or wrong, which
the protocol does not do (it counts decidable claims); the script was corrected and rerun and the first results file was deleted. The numbers below are the corrected run.

| RC-G | arm A (no guard) | arm B (guard on) |
| --- | --- | --- |
| paraphrases: shown / correct | 13 / 13 | 11 / 11 |
| negations: shown / wrong | 11 / **11** (all wrong) | 3 / **3** |
| negations: false Supported | **3** | **0** |
| fact-check matches blocked | | 10 (none unchecked for language) |
| degraded runs | 8 | 0 |
| A2 + RC-E (decidable): shown / correct / wrong | 52 / 51 / 1 | 51 / 51 / 0 |

| Rule item | result | verdict |
| --- | --- | --- |
| 1 informative (at least 6 wrong negations in A) | 11 | met |
| 2 wrong negations in B at most 25% of A | 3 of 11 = 27% (cluster bootstrap 95% interval 0% to 56%) | **NOT met** (one sentence over: 2.75 allowed) |
| 3 right paraphrases kept at least 85% | 11 of 13 = 84.6% | **NOT met** (one sentence under) |
| 4 right natural answers kept at least 90% | 51 of 51 | met |
| 5 no new wrong verdict | none | met |
| 6 no false Supported on RC-G in B | 0 (3 in A) | met |

**By the rule fixed before any data, the guard does not stay on. `live_match_guard` is false in the served config (the owner restarts the server to return to it).** The rule is not reinterpreted: two of six items fail, by one sentence each.
- **What the guard did:** 8 of the 11 wrong negated verdicts and all 3 false Supported removed; 2 of 13 right paraphrases became silent (a silent answer is not a wrong one); on A2 plus RC-E nothing right was lost and the one wrong verdict was removed. Together with RC-F (the English-only version removed 14 of 18) the direction is consistent.
- **The 3 remaining wrong negations are not fact-check answers:** they are answered by the Wikipedia evidence path (`path: evidence`, the validated two-model rule) that misreads a TRUE negated claim ("Pulse oximeter cannot show the oxygen level of pens and biscuits") as Refuted. The guard does not cover that path.
- **The danger in the served system stands:** with no guard, RC-G showed 11 wrong negated verdicts, 3 of them false Supported; this is recorded in the report. The code stays in the repo (tested, off).
- **A POST HOC option the owner may take:** switching the guard on anyway as a recorded owner decision (its safety effect is large and its cost is two silent answers), disclosed as not meeting the pre-registered rule. It would be labelled POST HOC and does not change this result.

## POST HOC owner decision (2026-10-06): the guard is switched ON although it did not meet its pre-registered rule
After the result above the owner decided to ship the guard (`live_match_guard: true` in `configs/pipeline/dev.yaml`). **This is a decision made after seeing the numbers and is labelled POST HOC; the result of the rule does not change: the guard FAILED items 2 and 3 by one sentence each.**
The case for it, as put to the owner: it removed all 3 false Supported and 8 of the 11 wrong negated verdicts on RC-G, removed the one wrong natural verdict and lost no right natural answer on A2 plus RC-E, and the only cost measured was 2 of 13 right paraphrase answers becoming silent
(a silent answer is not a wrong one); the English-only version on RC-F showed the same direction. The case against: the rule was written to prevent exactly this kind of after-the-fact choice. What this does NOT claim: that the guard is validated. The report carries the disclosure; the
3 remaining wrong negated verdicts (the Wikipedia evidence path) are untouched; and the guard's effect on a new sample has not been measured. To undo: set the key to false (one line) and restart.

## A false block, found by the owner on the demo forward (2026-10-06): POST HOC refinement of what the guard reads
The owner reported that "Pineapple juice is 500 times more effective at stopping a cough than cough syrup", which used to come out False (an already-published fact-check), stopped doing so. Tested on the running server: the claim matches a newsmeter.in fact-check whose claim text is
"Pineapple juice is 500% more effective than cough syrup. Is pineapple juice '500..." (rated False); **the guard blocked that match (P(contradiction) 0.62)** and the card fell back to "no verdict". This is the cost the protocol allowed for (a right answer made silent), but on the project's headline example, and it points at a design fault:
an NLI model does not read a question, or a headline followed by a question, as an assertion. Among the 10 matches the guard blocked in arm B of the test, 8 were correct blocks of negated claims; **2 were right answers silenced, and one of those two was a matched claim that is itself a question** ("Can Turmeric Ghee Shot Detox Liver In Two to Three weeks?", P(contradiction) 1.00).
**The refinement (POST HOC, decided after seeing these cases, not pre-registered):** the premise is the FIRST SENTENCE of the matched claim text, and when that first sentence is itself a question the match is not checked and stands ("not checked (the matched claim is a question)"). Everything else is unchanged (threshold 0.5, translation of Hindi and Punjabi, both match paths).
- **What this does and does not fix:** it restores the pineapple forward (the first sentence entails the claim) and the Turmeric paraphrase; it does not rescue the other blocked paraphrase ("Neem, coconut oil and kapur ...", a statement and a garbled translation). A negated claim matched to a question-form fact-check is no longer checked, so polarity-blind answers are possible there again; none of the 8 correct blocks in this test was of that kind.
- **Not validated on fresh data.** It was chosen from the cases above and RC-G is spent for it; the evidence is the cases themselves, 2 new unit tests, and a re-check of the demo forward on the restarted server. The report states this.

## A second false block (2026-10-06): POST HOC threshold change from 0.5 to 0.9
After the first-sentence refinement the owner restarted the server and the pineapple forward still came out "Be careful with this one". Tested again: the premise was now "Pineapple juice is 500% more effective than cough syrup." and the model still gave **P(contradiction) 0.77**, because "500 times" and "500%" are different numbers.
The protocol had assumed a different-number claim would read as Neutral; this model calls it a contradiction. Every contradiction probability the guard has produced so far: **correct blocks of negated claims: 27 of 28 at 0.94 or higher (RC-F v1: 0.9948 to 0.9996 for 13, plus 0.646 for one; RC-G: 0.94 to 1.00 for 9); wrongly blocked right answers: 0.62 (pineapple, whole text), 0.77 (pineapple, first sentence), 0.87 (the garbled "kapur" paraphrase), 1.00 (a question, now skipped).**
A true negation is a confident contradiction and a number or wording mismatch is a middling one. **The threshold is therefore raised to 0.9 (`LIVE_MATCH_GUARD_P`).** This is POST HOC and was chosen by looking at exactly these numbers on spent sets, so it is not validated: it is the cut a human would draw through a bimodal list, and a fresh sample may sit differently. Consequences, stated before any re-run: of the 28 correct blocks one (0.646) would be released, and different-number claims matched to a fact-check of a similar claim
are answered with that fact-check's verdict, as they were before the guard existed. The two refinements together turn the guard into "block only a confident, whole-claim contradiction". A measurement on fresh sentences would need a new sheet; none is planned.
