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
