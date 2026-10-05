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

