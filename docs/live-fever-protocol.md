# Live verdict on FEVER: protocol and decision rule (pre-registered)

Written and committed BEFORE the FEVER data is downloaded, any code for it exists, or
any claim is run. Approved by the project owner on 2026-10-04 (the rule change, the
5% / 80% bars, and the BART-large-MNLI download). Nothing below may be changed after
the first claim is run; a change would be a new, separately logged protocol.

## Why this replaces the probe-set rule

Four hand-written probe sets (`docs/live-search-probe.md`) rejected the live verdict by
the rule "no correct answer may turn wrong". The live-wrong count went 5, 5, 2, 1, but
a set of ~38 claims cannot measure a rate, and one miss rejects the whole path with no
confidence interval either way. This protocol measures the rate that matters (a false
claim called Supported) on enough claims to put an interval on it. The probe-set rule is
superseded for the adoption decision; the probe sets are still reported as context.

## Data

FEVER dev (`copenlu/fever_gold_evidence`, `valid.jsonl`, 15,935 claims; CC BY-SA 3.0).
Labels SUPPORTS / REFUTES / NOT ENOUGH INFO map to Supported / Refuted / NEI.
Two DISJOINT class-balanced samples, seed 42, drawn by `src/data/loaders.py`:

| Set | n | Used for |
| --- | --- | --- |
| `fever_select` | 150 (50 per class) | choosing among variants V1-V3 ONLY |
| `fever_confirm` | 300 (100 per class) | the one adoption decision |
| `fever_confirm_sub` | 60 (20 per class), a subset of `fever_confirm` | Hindi and Punjabi check |

The Hindi and Punjabi check translates the 60 English claims with NLLB (en->hi, en->pa)
and runs them through the live pipeline, which translates them back. It tests the
Hindi/Punjabi path, not natural Hindi or Punjabi text, and is reported as a round-trip
test.

**Caveat, stated now:** DeBERTa-v3-large-mnli-fever-anli-ling-wanli was trained on
FEVER-NLI training claims. FEVER dev claims were not in that training set, but the
domain is familiar to it, so FEVER numbers are OPTIMISTIC for this model on real
WhatsApp forwards. The 5% and 80% bars are set tight for that reason.

## What is run

The real `Orchestrator.verify(claim, live=True)`, exactly as the UI button does it
(config `configs/pipeline/dev.yaml` with `live_search`, `live_verdict` and
`live_translate` on, the entity-grounding gate on). Each judged passage is stored with
its stance probabilities from three NLI models (DeBERTa-v3-large, BART-large-MNLI,
mDeBERTa-xnli), so variants are computed offline from the same stored evidence; the
network is hit once per claim. Predictions are scored through `src/eval/evaluate.py`.

## Variants (fixed now)

- **V0** the served offline pipeline, no live search (the "before").
- **V1** the current live path: DeBERTa-v3-large alone.
- **V2** V1, but Supported or Refuted is kept only if BART-large-MNLI gives the same
  stance on the same judged passages; otherwise NEI.
- **V3** like V2 with mDeBERTa-xnli as the second model.
- **Always-NEI** (what the button does today: no verdict) is the dumb baseline.

"Agree" means: the relevance-weighted verdict (`live_verdict`, unchanged) computed from
each model's probabilities separately gives the same verdict, and that verdict is
Supported or Refuted; any disagreement gives NEI.

**Selection (on `fever_select` only):** the variant with the fewest false-Supported
calls among V1-V3; ties go to the higher accuracy on answered claims; a further tie
goes to V1 (the simplest). The chosen variant is run on `fever_confirm` exactly once.

## Decision rule (on `fever_confirm`, English, 300 claims)

A variant is ADOPTED only if all four hold:

1. **False-Supported rate.** Among the 200 claims whose gold is Refuted or NEI, the
   share answered Supported has a 95% Wilson upper bound <= 5%. That is at most 3 of 200 (4 of 200 has an
   upper bound of 5.03% and fails).
2. **Accuracy on answered claims** (a claim is answered if the verdict is Supported or
   Refuted) >= 80%, and higher than V0's accuracy on the same claims' answered subset.
3. **Hindi and Punjabi.** In each 60-claim round-trip subset, at most 2 false-Supported
   calls among the 40 claims whose gold is not Supported.

4. **It must say something.** Among the 200 claims whose gold is Supported or Refuted, at
   least 20% (40 claims) are answered CORRECTLY (a Supported call on a Supported claim, a
   Refuted call on a Refuted claim). Added by amendment below.

Reported but not gating: coverage (share answered), per-class precision and recall, the
confusion matrix, latency, and the variant's behaviour on probe sets 2-4.

## If it passes

The live button shows the verdict, labelled "online result, confidence not calibrated",
with the sources. `live_verdict` and `live_translate` go on in
`configs/pipeline/dev.yaml`, the UI strings are updated (reviewed by the owner), and the
report (section 8b), SRS FR-28, SYSTEM_DESIGN section 15 and UI_UX section 5 are
revised. No test-split number changes: live search never runs in an evaluation.

## If it fails

Live stays evidence-only and this protocol's results are written up as a measured
failure, with the numbers. No further variants are tried on `fever_confirm`.

## Allowed re-runs

A claim whose evidence was not fetched because a source returned HTTP 429 or a network
error is re-run once after a pause and counted once (as in the probe runs; both runs are
kept). Nothing else is re-run. Bugs in the harness found before `fever_confirm` is run
are fixed and logged; after that, none.

## Corrections after commit (logged, none after any run)

- 2026-10-04, before any code or data: the first version said "at most 4 of 200" for the
  false-Supported bound. 4/200 has a Wilson upper bound of 5.03%, which is above 5%, so
  the rule as stated (upper bound <= 5%) allows at most 3. The parenthetical was an
  arithmetic slip, not a change of rule; the rule's wording is unchanged.
- 2026-10-04, before any claim is run: **what a prediction is.** The scored prediction is
  what the user would be shown: the verdict if the card is not abstained (confidence at or
  above the served tau_abstain, 0.3835), otherwise NEI ("not enough to judge"). A card
  that is NotAClaim also scores as NEI. "Answered" in the decision rule therefore means a
  Supported or Refuted prediction. For V2 and V3 the confidence is the LOWER of the two
  models' confidences. V0 (offline) and V1-V3 are scored the same way. The consistency of
  the harness is checked by recomputing V1 from stored probabilities and comparing with the
  live card, claim by claim; any mismatch is reported.
- 2026-10-04, **amendment, before any decision-set (`fever_confirm`) claim was run**: rule 4
  was added. As first written, a variant that answered almost nothing could pass rules 1-3
  trivially (a button that always says "not enough to judge" has a false-Supported rate of
  zero), and shipping it would add nothing to the evidence-only button. A smoke test of
  three `select` claims (all came back NEI) made the gap visible; the threshold, 20% of
  the 200 checkable claims, was chosen from the design (below it the verdict would be
  absent for four checkable claims in five), not from any result. The three smoke claims
  stay in `select`'s results.

## Results log (appended as the protocol runs)

**Selection on `fever_select` (150 claims, 2026-10-04), per the rule above.** All 150 claims
collected with no source failure after the allowed single re-run of failed claims; the
harness check (V1 recomputed from stored probabilities equals the live card) matched on all
150. Scored through `make eval`:

| Variant | false-Supported (of 100 non-Supported) | accuracy on answered | answered | run |
| --- | --- | --- | --- | --- |
| V0 offline served | n/a | 0.333 (all claims) | 150 | 48450ff742a6 |
| always-NEI | 0 | n/a | 0 | a50ae015db7b |
| V1 DeBERTa alone | 6 | 0.772 | 57 | a381431fe5ae |
| V2 DeBERTa + BART agree | **3** | 0.804 | 51 | 5d9a0b582923 |
| V3 DeBERTa + mDeBERTa agree | 5 | 0.812 | 48 | a56335e8f73d |

**Chosen: V2** (fewest false-Supported). It is now run once on `fever_confirm` (300).

**Decision run on `fever_confirm` (300 claims, English), V2 as chosen, 2026-10-04.** All 300
claims collected; 11 had a source failure and were re-run once as allowed (0 remain); V1
recomputed from stored probabilities equals the live card on all 300; 3 claims produced more
than one extracted claim and fall back to the card for every variant. Scored through
`make eval` (never from the harness):

| Variant | false-Supported (of 200) | Wilson upper | answered | accuracy on answered | correct on the 200 Supported/Refuted claims | run |
| --- | --- | --- | --- | --- | --- | --- |
| V0 offline served | 0 | 1.9% | 292 | 0.336 | 98 | f7bbd41c0314 |
| always-NEI | 0 | 1.9% | 0 | n/a | 0 | 1222822e4bbb |
| V1 DeBERTa alone | 5 | 5.7% | 116 | 0.793 | 92 | dd0046decf08 |
| **V2 DeBERTa + BART (chosen)** | **3** | **4.3%** | 104 | **0.788** | 82 | 4baa98b87ce4 |
| V3 DeBERTa + mDeBERTa | 4 | 5.0% | 103 | 0.883 | 91 | 41d5bebd6787 |

The decision rule applies to V2 only (the variant chosen on `select`):

1. False-Supported upper bound <= 5%: **PASS** (3/200, upper 4.32%).
2. Accuracy on answered >= 80% and above V0's: **FAIL** (82 of 104 = 78.8%; V0's 33.6% is beaten,
   but the 80% bar is missed by 1.2 points, i.e. 2 claims: 84 right of 104 would have passed).
3. Hindi and Punjabi subsets: not decisive once rule 2 fails; run for the record.
4. At least 20% of the 200 checkable claims answered correctly: **PASS** (82/200 = 41%).

**Outcome: V2 is NOT adopted.** Per the protocol no other variant is tried on `fever_confirm`.
For the record, and not as a decision: V3 would have passed rule 2 (88.3%) and failed rule 1 by
one claim (4/200, upper 5.03%); V1 fails rule 1 (5.7%). Live search stays evidence-only.

Reading the numbers honestly: V0's "98 correct on the 200" is the claim prior at work (it calls
nearly everything Refuted, so it is right on the Refuted half and wrong on the rest, 33.6%
accuracy), while the live variants answer about a third of the claims and are right about four
times in five. The live verdict is a real gain in precision, with low coverage, and a
false-Supported rate near the 5% line that the protocol set.

