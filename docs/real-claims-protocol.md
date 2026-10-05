# The live check on real claims: measurement protocol (pre-registered)

**Status: written 2026-10-05 and committed BEFORE any real claim has been run through the live check.** Not changed afterwards except by dated
corrections. Approved by the owner the same day (sets: AVeriTeC plus the owner's forwards; run through the owner's running server).

## Why

Every live-check number so far (94.3% precision, 3 false "Supported" in 225, about 30% coverage) comes from FEVER claims, which are Wikipedia-style
sentences, with a model trained on FEVER-style data (`docs/live-fever-protocol-2.md`). Nobody has measured it on claims people really circulate. This
protocol does that once, as a **measurement**: the served system is frozen and nothing in this run changes it. Its job is to say how much of the FEVER
result transfers and to give the next improvement a baseline and an error list.

## The two sets

| Set | Claims | Truth | Use |
| --- | --- | --- | --- |
| **RC-A** AVeriTeC dev | all 500 `data/splits/averitec/dev.jsonl` claims (real fact-checked claims, mostly news and politics, 2019-2021) | the fact-checkers' own label: Supported -> true (T), Refuted -> false (F), Not Enough Evidence and Conflicting -> unverifiable (U) | held-out structure below |
| **RC-B** the owner's forwards | at least 100 real forwarded messages the owner supplies (family groups, social media), one claim each, kept in the gitignored `data/private/real_forwards.csv` (never committed) | the owner labels each T, F or U with a one-line source for the label, BEFORE the run | analysed in full |

**RC-A is split once, now:** shuffle the 500 uids with seed 42 and take the first 250 as **A1 (explore)** and the last 250 as **A2 (locked)**. Failure
cases may be read from A1 only. A2's per-claim results are written to disk but **no A2 error is read** until a later improvement is final and is tested once
on A2. RC-B is never used to tune anything.

## What is run

The served pipeline exactly as the demo uses it: `POST /verify` with `live_search: true` on the owner's running server (config `configs/pipeline/dev.yaml`),
claim text as written, no `force_claim`. A claim the claim gate refuses counts as "not checked" and stays in every denominator. Per claim we store:
the path (fast, evidence, none), whether a verdict was shown (Supported or Refuted, not abstained), which source decided it (a published fact-check
match, or the two-model Wikipedia rule), the live sources used, and seconds. An HTTP 429 or a degraded source is re-run once (as protocol 2 allowed);
both runs are kept. The run is resumable and sequential.

## What is reported (all computed by `eval.metrics`, none inline)

For each of A1, A2 and A1+A2, and for RC-B:
- **Coverage:** claims with a shown verdict / claims.
- **Precision on decidable claims:** among shown verdicts on gold T or F, the share whose verdict matches (Supported on T, Refuted on F), with a Wilson 95% interval.
- **False-Supported rate:** shown "Supported" on gold F, as a share of gold-F claims, with its Wilson 95% interval and the raw count.
- **Verdicts on unverifiable claims:** shown verdicts on gold U, counted separately and not as errors or as successes.
- By decider: the same numbers for verdicts that came from a published fact-check and for those from the two-model Wikipedia rule.
- The FEVER reference numbers beside them, without a significance test (the sets differ).

## How the result is read (rule fixed now)

The check **transfers** if, on A1+A2 decidable claims, precision is at least **85%** with a Wilson lower bound of at least **80%**, **and** the false-Supported
rate has a Wilson upper bound of at most **8%**. It **partly transfers** if exactly one of those holds. Otherwise it **does not transfer**. Whatever the
outcome, the served rule is not changed by this run, the result goes into the report's limitations and the log, and a failing result names the
improvement to try first (the error causes come from A1 and RC-B only). Coverage has no bar here; it is reported.

## Honest limits

- AVeriTeC claims are news claims, many of them about people and events Wikipedia covers thinly, so low coverage there says little about WhatsApp claims.
- The fact-checkers' label on AVeriTeC is itself a judgement, and "unverifiable" is not an error for a system that stays silent.
- RC-B is small and labelled by one person, so its intervals are wide; it is the closest to the real use and the least statistical.
- A published fact-check found through Google counts as a verdict from the product, but it is the fact-checkers' verdict, not the model's: the by-decider split keeps them apart.
- Live sources change daily; the run is a snapshot of one day (2026-10-05 or later) and is cached under `data/interim/live_cache`.

## Dated corrections

**Correction 1 (2026-10-05, before RC-B is run; RC-A had been started and is untouched).** The owner's file for RC-B (`real_forwards_fresh_120.csv`, copied to the
gitignored `data/private/real_forwards.csv`) is **120 written claims, not collected forwards**: 100 in Roman Hindi and 20 in Roman Punjabi, each labelled by the
owner with an institutional source (WHO, NPCI, UIDAI, ISRO, ECI and others), 45 T, 66 F and 9 U, and none of them copied from a family group. It is therefore
reported as **"RC-B: owner-supplied claims in the style of forwards"**, never as real WhatsApp forwards, and the report must say so. Five rows (91, 117, 118,
119, 120) carry commentary about their own verifiability inside the claim text (for example "this number is not verified"); all five are labelled U, which is
never counted as an error, but they are listed in the result and the result is also given without them. The rule for reading RC-B is the protocol's rule applied
to its decidable (T and F) claims, with the caveat above that 111 decidable claims give wide intervals. RC-A is unchanged and remains the main
measurement.

**Correction 2 (2026-10-05, before RC-B or RC-C is run).** The owner supplied a second file, `real_forwards_chatty.csv` (copied from
`real_forwards_120_lang_updated (1).csv`): **the same 120 claims, same ids and the same labels** (45 T, 66 F, 9 U), rewritten as chatty forwards (English and
Roman Hindi or Punjabi mixed, emoji, questions, and for most rows the correction written inside the message: "nope", "actually the whole point is...",
"the claim is wrong"). It is run as **RC-C** and reported separately and **never** used for the transfer rule, because the message often states its own verdict, so the
checker may be reading the correction and not the claim. The plain RC-B file stays the set the rule is read on. RC-C answers a different question: how much the
shown verdicts move when the same claims arrive wrapped in a chatty forward (the claim extractor, language handling and the NLI model all see more text),
measured by pairing each id's RC-B and RC-C result (`eval.metrics.paired_flip_counts`: both silent, silent to shown, shown to silent, same verdict, flipped,
and correct in each). Rows 91 and 117-120 remain flagged in both files.


**Correction 3 (2026-10-05, before RC-B or RC-D is run; RC-A still running and untouched). RC-C is withdrawn and RC-D replaces it.** The owner supplied a third file
(`real_forwards_collected_new.csv`, copied to the gitignored `data/private/real_forwards_triplets.csv`): 120 rows that are **40 claims, each in three renderings**
(English, Roman Hindi or Roman Punjabi, and for 20 of them Devanagari or Gurmukhi), 42 T, 63 F and 15 U, wrapped in templated forward phrases ("Guys, got this
in a group", "pls check before forwarding", "true or fake??"). They are written claims, not collected forwards (the owner could not give dates), and the three
renderings of a claim are **not independent**. Decisions, all fixed before any of these rows is run:
- **RC-B (`real_forwards.csv`, the plain 120) stays the one set the transfer rule is read on.** It has the most distinct claims and clean text. The chatty-rewrite
  file of correction 2 (RC-C) is **deleted and withdrawn**; its question is covered by RC-D and nothing was run on it.
- **RC-D is the language-triplet set.** It is never used for the transfer rule. It answers: does the same claim get the same shown verdict in English, in Roman
  letters and in native script (the project's romanization question), and how often is the checker silent in each language?
- **Six rows are dropped before the run** because the text states its own verdict, so the label can be read either way (rows 8, 9, 14, 15, 68, 83: for example row 8
  says antibiotics do not cure viral colds, which is TRUE, but is labelled F). The owner's labels are not changed; the rows are excluded and listed. 114 rows, 40 clusters, remain.
- **Statistics respect the clusters:** precision and its 95% interval come from a bootstrap that resamples whole clusters (`eval.metrics.cluster_precision_ci`, seed 42), never
  from a Wilson interval over rows; per-language coverage and precision are reported; consistency across a cluster is counted by `eval.metrics.cluster_consistency`
  (all silent, all shown and agreeing, silent in some renderings, shown but disagreeing).
- Rows 91 and 117-120 of the plain file and the templated wrappers are disclosed in the report; RC-D is described there as "owner-supplied written claims in three renderings".

**Correction 4 (2026-10-05, before RC-B or RC-D is run; RC-A is complete and untouched). The owner supplied a fourth file, which replaces the plain 120 as RC-B.**
`real_forwards_collected.csv`, copied to the gitignored `data/private/real_forwards.csv` (the earlier plain-120 file is overwritten and is no longer used):
**150 written claims** with a source column, a language, a month and a "where seen" column: 75 F, 50 T, 25 U (the U rows are "no public source settles this local claim" tests
of staying silent); English 43, Roman Hindi 47, Hindi 35, Gurmukhi Punjabi 14, Roman Punjabi 11. It is better than the earlier files because the claims are distinct
(25 source families, not one claim in several languages), the false ones imitate real scam forwards (the "WhatsApp will charge Rs 2 per message" chain, "PM Free
Recharge", India Post and EPFO scams, LPG refill rules), and it has native-script rows and local unverifiable claims. Limits, stated before the run:
- **Not collected forwards.** The month and "where seen" columns cannot be verified and are never used in any analysis; the set is reported as "owner-supplied written claims
  modelled on real forwards". Some are near-duplicates in different languages (the WhatsApp-charging message appears five times).
- **Source column errors that do not change a label:** rows 60 and 84 (zero gravity near the ISS), 80 and 137 (lemon water and cancer) cite a page that does not discuss
  the claim; the labels F stand, and the rows are listed in the report.
- **Clusters:** a cluster is a **source family** (the `source_for_label` string, 25 of them), because claims on one topic are not independent. The transfer rule is applied
  twice, on the row-level Wilson intervals and on cluster-bootstrap intervals (`eval.metrics.cluster_rates_ci`, seed 42, 1000 resamples), and **the more conservative verdict
  stands** (`eval.metrics.transfer_verdict_with_clusters`). Both numbers are reported.
- RC-D (the language triplets) is unchanged and remains a separate, small language-consistency check, never used for the rule. RC-A is the main measurement and RC-B the
  second; if they disagree, both are reported and the more conservative reading is the headline.

## Result (2026-10-05; run `80932a36cbf2`, `results/80932a36cbf2.json`; served system unchanged, owner's running server)

Read against the rule fixed above. Nothing was changed because of these numbers. A2's errors were not read.

| Set | Claims | Shown | Coverage | Decidable shown | Correct | False Supported | Rule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A (AVeriTeC dev) | 500 | 61 | 0.122 | 56 | 56 | 0 of 305 false | transfers |
| A1 | 250 | 30 | 0.120 | 28 | 28 | 0 of 150 | transfers |
| A2 | 250 | 31 | 0.124 | 28 | 28 | 0 of 155 | transfers |
| B (owner's 150 written claims) | 150 | 6 | 0.040 | 6 | 4 | 0 of 75 | partly transfers |
| D (triplets, 114 rows, 40 clusters) | 114 | 6 | 0.053 | 6 | 5 | 0 of 57 | partly transfers |

- **RC-B by source family** (25 clusters): precision 0.667, 95% interval 0.25 to 1.0; false-Supported 0 of 75. The conservative verdict is **partly transfers**: the
  false-Supported bar holds, the precision bar cannot be met on 6 shown verdicts (Wilson lower bound 0.30).
- **Where the verdicts came from.** A: 55 of 61 from a matched fact-check (50 of 50 decidable correct), 6 from Wikipedia (6 of 6). B: 1 fact-check (1 of 1), 5 Wikipedia (3 of 5).
  D: 2 fact-check (2 of 2), 4 Wikipedia (3 of 4). On A, 5 verdicts were shown on claims whose gold is "not enough evidence" (excluded from precision; reported).
- **Coverage collapses outside FEVER:** about 30% on FEVER (protocol 2), 12.2% on AVeriTeC dev, 4.0% on the owner's written claims. The live check is silent far more often on real claims.
- **Wrong answers on B and D** (all three are TRUE claims shown "Refuted" from Wikipedia, in Roman Hindi or Roman Punjabi): the Constitution coming into force on 26 January 1950
  (B), reporting cyber fraud to 1930 (B), the Aadhaar VID claim (D). A1 has none. Causes are NOT yet tallied: a taxonomy is fixed before any silent case is read.
- **RC-D language consistency:** of 40 claims, 35 silent in every rendering, 5 shown in some renderings and silent in others, 0 shown in all three, 0 shown with disagreeing verdicts.
  Shown by rendering: English 0 of 40, Hindi (Devanagari) 2 of 10, Hindi (Roman) 2 of 36, Punjabi (Gurmukhi) 1 of 10, Punjabi (Roman) 1 of 18 (the Roman Punjabi one is the wrong answer).
  Six shown verdicts cannot say that language matters; they say the checker is mostly silent in every rendering.
- **Reading:** where the check speaks it is right on AVeriTeC (56 of 56) and never called a false claim Supported anywhere (0 of 437 gold-false). It does not yet carry real
  forwards: it is silent on 96% of the owner's written claims, and its few Wikipedia verdicts on Roman-script claims include true claims called Refuted.
  Limits: B and D are written claims, not collected forwards; 6 shown verdicts are too few for a precision claim in either direction.
