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
