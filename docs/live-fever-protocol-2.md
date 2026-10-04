# Live verdict on FEVER, protocol 2 (A+): fresh claims, real-world truth, pre-registered fallback

**Status: APPROVED by the project owner on 2026-10-04** (350 claims; false-Supported upper bound
<= 5%; precision >= 90% with Wilson lower bound >= 85%; 20% coverage; <= 2 false-Supported per
language on the round trip; the owner labels the 100 NEI claims). Committed BEFORE the fresh
sample is drawn; no fresh data has been drawn and no claim has been run at this commit. Not
changed afterwards except by dated corrections at the bottom.

## Why a second protocol

Protocol 1 (`docs/live-fever-protocol.md`) ran once. Variant V2 (DeBERTa-v3-large and
BART-large-MNLI must agree) failed its accuracy bar by two claims: 82 right of 104 answered
(78.8%) against 80%. Reading its errors afterwards showed that the bar measured FEVER's label
convention as much as the system: 22 of the 32 errors in the two sets were claims FEVER labels
"not enough info" that V2 called Refuted, and most of those are absurd claims that ARE false
in the real world; on claims with a decidable FEVER label V2 was right 123 of 129 times (95%).
That reading was made after the run, so it cannot rescue protocol 1, and **protocol 1's result
stands in the report as a failed pre-registered rule, with both numbers.** This protocol tests
the improved question on claims nobody has seen.

## Data

Fresh claims from FEVER dev (`copenlu/fever_gold_evidence`, valid.jsonl, CC BY-SA 3.0), seed 42,
disjoint from `fever_select` and `fever_confirm` (by FEVER id and by normalised text), balanced
toward what the gates need:

| Set | n | Composition |
| --- | --- | --- |
| `fever_fresh` | 350 | 100 gold Supported, 150 gold Refuted, 100 gold NOT-ENOUGH-INFO |
| `fever_fresh_sub` | 60, a subset | 20 of each gold label, for the Hindi and Punjabi round trip |

Gold Refuted is 150 so that a 5% upper bound on false-Supported is reachable (at most 2
errors in 150 gives 4.7%; at most 1 in 100 would give 5.4%).

## Real-world truth labels (the change from protocol 1)

Every fresh claim gets a **real-world truth**: `T` true, `F` false, `U` unverifiable (nothing
public settles it).

- Gold Supported -> `T`. Gold Refuted -> `F`. (FEVER's own labels, as in protocol 1.)
- Gold NOT-ENOUGH-INFO -> labelled by the **project owner**, one claim at a time, from the claim
  text ALONE (no system output, no FEVER label shown), shuffled. They may look facts up. These 100
  labels are committed (`data/probe/fever_fresh_nei_truth.json`) BEFORE any claim is run.

## What is run

Exactly V2 of protocol 1, no selection step, no other variant: the real
`Orchestrator.verify(claim, live=True)` (gated English route, `configs/pipeline/dev.yaml` with
the live flags on), each judged passage scored by DeBERTa-v3-large and BART-large-MNLI, the two
live verdicts must agree and be Supported or Refuted, else NEI; the answer is shown only above
tau_abstain 0.3835, otherwise NEI. Scored through `src/eval/evaluate.py` (a classification run
with the real-world truth as gold; `T/F/U` map to Supported/Refuted/NEI). One run, with the
single allowed re-run of claims where a source failed.

An answer is **correct** if Supported on `T` or Refuted on `F`; **harmful** if Supported on `F`
or `U`, or Refuted on `T` or `U`; NEI is never wrong.

## Gates (on `fever_fresh`, English, 350 claims)

1. **False-Supported.** Among the claims whose truth is `F` or `U`, the share answered Supported
   has a 95% Wilson upper bound <= 5%.
2. **Precision of the answers.** correct / answered >= 90% as a point estimate AND the Wilson
   lower bound >= 85%.
3. **It must say something.** At least 20% of the 250 gold Supported/Refuted claims (50 claims)
   are answered correctly.
4. **Hindi and Punjabi.** On `fever_fresh_sub` translated en->hi and en->pa (NLLB) and run through
   the pipeline, at most 2 false-Supported answers among the claims whose truth is `F` or `U`, in
   each language. Reported as a round-trip test, not natural Hindi or Punjabi.

Reported but not gating: coverage, per-class precision and recall, the confusion matrix against
both the FEVER labels and the real-world truth, latency, the harmful answers one by one.

## What happens next, decided now

The project owner has decided the live verdict will ship in the button in either case; the
protocol decides only HOW it is described.

- **All four gates pass:** it ships labelled as validated on a pre-registered fresh set.
- **Any gate fails:** it still ships, as the owner's explicit override, labelled "experimental,
  not validated: it missed its pre-registered bar", and the label shows the numbers of BOTH
  runs.
- **In either case every number is reported, together:** protocol 1's (78.8% against the FEVER
  labels; about 95% on claims with a decidable FEVER label, post-hoc) and protocol 2's, whatever
  they are. A fresh run is never dropped from the report, and the report states which numbers
  were pre-registered and which were read after the fact.

## What shipping changes in the code (and only then)

After the run, not before: the two-model agreement (V2) is added to the live path of the
orchestrator, BART-large-MNLI joins the live NLI models, `live_verdict` and `live_translate`
go on in `configs/pipeline/dev.yaml`, the card is labelled "online result, confidence not
calibrated", the new UI strings are reviewed by the owner in hi/pa, and a regression test and a
GPU-memory check cover it. The AVeriTeC dev run must stay byte-identical (live search never runs
in an evaluation); no test-split number changes.

## Allowed re-runs and corrections

A claim whose evidence was not fetched because a source returned HTTP 429 or a network error is
re-run once after a pause and counted once. Harness bugs found before the first fresh claim is
run are fixed and logged; none after. Corrections to this document are appended below with the
date and the reason, and none after the first fresh claim is run.

## Results (2026-10-04), V2 on `fever_fresh`: ALL FOUR GATES PASS

Collected as pre-registered: the owner's 100 real-world labels (60 false, 25 true, 15
unverifiable) were committed (`989231d`) before any claim ran; all 350 claims were collected
with 0 source failures remaining after the one allowed re-run; V1 recomputed from stored
probabilities equals the live card on all 350; 4 claims produced more than one extracted claim
and fall back to the card. Scored through `make eval`; gates read by `scripts/live_fever.py decide`.

Real-world truth of the 350 claims: 125 true, 210 false, 15 unverifiable. Of the 100 claims
FEVER labels "not enough info", 60 are false in the real world and 25 are true.

| Scored against real-world truth | answered | correct | false-Supported (of 225 false/unverifiable) | run |
| --- | --- | --- | --- | --- |
| V0 offline served | 345 | 208 (the claim prior) | 0 | e3044f2aa461 |
| always-NEI | 0 | 0 | 0 | d5c6001307a0 |
| **V2 live** | **106** | **100** | **3 (upper bound 3.85%)** | e68b4fb0e342 |

Against FEVER's own labels (run 01f902e6b7ad) V2 answered the same 106 claims, 92 of them
matching FEVER's label; the 8 differences are claims FEVER calls "not enough info" that are
true or false in the real world (the point of this protocol).

| Gate | Needed | Result | |
| --- | --- | --- | --- |
| 1 False-Supported among false or unverifiable claims | Wilson upper <= 5% | 3 of 225, upper 3.85% | PASS |
| 2 Precision of the answers | >= 90% and lower bound >= 85% | 100 of 106 = 94.3%, lower 88.2% | PASS |
| 3 Says something | >= 50 correct on the 250 gold Supported/Refuted claims | 92 | PASS |
| 4 Hindi and Punjabi round trip, <= 2 false-Supported each | <= 2 | hi 0 of 33, pa 1 of 33 | PASS |

Hindi (round trip, 60 claims): 20 answered, 20 correct (runs 6b6fa07615a9 truth, b1fa27cecdda
FEVER). Punjabi: 18 answered, 17 correct (runs 02beb46a95df truth, 6ca277ce2a4b FEVER). Latency of
the live path: median about 5 s per claim in the harness.

**Every wrong answer (6 of 106), none hidden:**

| Claim | Real-world truth | V2 said | Why |
| --- | --- | --- | --- |
| Tottenham Hotspur F.C. is Chinese. | false | Supported | the page is about the club; the NLI read "Chinese" loosely (the club's ownership, not its nationality) |
| Don Bradman had years in which things happened. | unverifiable (vacuous) | Supported | a claim too vague to refute; the page trivially "supports" it |
| Literacy arts has been significantly impacted by Appropriation (art). | unverifiable | Supported | vague claim, topical page |
| Papua comprised all of a country. | true | Refuted | the NLI read "all of" as contradicted by the page |
| Chile is not a stable nation. | true | Refuted | a negated claim read against a page that never says it |
| Lalla Ward was declared Sarah Ward. | true | Refuted | the page states her birth name differently from the claim's phrasing |

**Coverage is low and stated plainly:** V2 gives a verdict on 106 of 350 claims (30%) and says
nothing on the rest. Caveats that must travel with the numbers: the claims are FEVER's
Wikipedia-style claims, not WhatsApp forwards; DeBERTa-v3-large has seen FEVER-style training
data, so the numbers are optimistic for real forwards; the Hindi and Punjabi runs are a
round trip through machine translation, not natural text; and the real-world labels of the 100
"not enough info" claims are one person's judgement.

**Reporting.** Protocol 1 (V2 failed its accuracy bar by two claims, 78.8% against FEVER's
labels, about 95% on claims with a decidable FEVER label read after the fact) and this
protocol (pre-registered, fresh claims, all gates passed) are reported together in the report.
Per the pre-registered decision above, the live verdict ships, labelled as validated on a
pre-registered fresh set, with the numbers of both protocols.

