# Model card: TruthLens claim verification

Follows the structure of Mitchell et al., "Model Cards for Model Reporting" (2019), adapted to a system of several models.
Numbers are the project's own and each carries its results file; the report ([`report.md`](report.md)) is the full record.

| | |
| --- | --- |
| **System** | TruthLens v1.0, a pipeline of pretrained and fine-tuned models, not one model |
| **Date** | 2026-10-12 |
| **Author** | Soumirya Sarangi (CSE472 student project) |
| **Code licence** | MIT; third-party models and datasets: [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) |
| **Training data** | AVeriTeC (CC BY-NC 4.0), MultiClaim (restricted), X-CLAIM, CheckThat! 2025 Task 2 |

## Intended use

- **Primary:** a reader checks a forwarded message in English, Hindi or Punjabi (native or Roman script) and sees whether
  it has been fact-checked, the sources, and plain-language uncertainty.
- **Primary users:** ordinary readers, often older relatives; evaluators of the project.
- **Secondary:** research on the romanization penalty, calibration and abstention for claim verification.

## Out of scope: do not use it for

- Deciding what is true on its own, or as the sole basis for any consequential decision.
- Moderation, takedown or enforcement, or scoring people or accounts.
- Opinions, predictions, satire, religious or political belief, or personal medical, legal or financial advice.
- Languages other than English, Hindi and Punjabi (it refuses them).
- Any commercial use without checking the non-commercial terms of the training data and of NLLB-200.

## Factors

Performance depends on: **script** (native vs Roman), **language** (Punjabi has about 346 X-CLAIM training examples and
is the weakest), **whether the claim was ever fact-checked** (the fast path and the fact-check route work only then),
**topic coverage of Wikipedia**, and **negation**.

## Metrics and results

Chosen because accuracy is misleading here (the majority class is about 61% of AVeriTeC): macro-F1 over five classes,
always beside the majority baseline; ECE for confidence; coverage and precision at a threshold for the fast path.

| Component | Metric | Result | Run |
| --- | --- | --- | --- |
| Offline verdict (test) | macro-F1 | 0.2622 vs always-Refuted 0.1447 vs claim-only control **0.3085** | `0c41481ee90d`, `36e3f8e6094c` |
| Retrieval | Success@10 | 0.1531 | `3cd7a0719b5b` |
| Confidence | ECE (test) | 0.039 after scaling | `c3128d753fc7` |
| Fast path (τ 0.90) | coverage / precision | 1.7% / 81% | `891eecc6a90e` |
| Claim spans, romanization penalty | token F1 | Hindi −0.068, Punjabi −0.061 | report §7 |
| Live verdict (FEVER-style, 350 fresh) | precision / false Supported | 100 of 106 / 3 of 225; about 30% coverage | `docs/live-fever-protocol-2.md` |
| Live check, AVeriTeC dev (500) | shown / right / false Supported | 61 / 56 of 56 / 0 of 305 | `80932a36cbf2` |
| Live check, 150 owner-written claims | shown | 6 (96% silent) | `80932a36cbf2` |
| Served, fact-check threshold 0.70 | shown / right / false Supported | 56 / 51 of 52 / 0 of 205 | `f0d7ab316ff0` |

The headline negative result: **the offline verdict does not beat a control that never reads the evidence**, because
retrieval puts a gold document in the top 10 for only 15% of claims.

## Evaluation data and its limits

- The locked test split was run **once**; nothing afterwards changed a reported number.
- The live check was validated on FEVER-style claims, on AVeriTeC dev, and on **owner-written** claims (150 + 85 + 78
  sentences). These are written claims modelled on real forwards, **not collected forwards**. There is no sample of real
  WhatsApp traffic, and no usability study with the intended readers has been run.
- Several improvement attempts failed their pre-registered rules and were not shipped (`docs/*-protocol.md`).

## Ethical considerations and risks

- **False reassurance.** A wrong "true" can spread a falsehood. The live rule was built to make false "Supported" rare
  (0 of 305 and 0 of 205 in the two real-claims measurements), and every card says it can be wrong.
- **False accusation.** A wrong "false" can discredit a true message. Verdicts show their source so a reader can disagree.
- **Negation blindness.** A fact-check match carries no polarity. On 39 fresh negated claims the unguarded system showed
  11 verdicts, **all wrong, 3 of them false "Supported"**. A guard cut that to 3 wrong and none false "Supported", but
  failed its pre-registered rule by one sentence on two items and is served on an explicit, post hoc owner decision
  (`docs/polarity-guard-v2-protocol.md`, run `b3a6fdfb6933`). Its effect on a new sample is unmeasured.
- **Silence as a failure mode.** On real forwards it mostly says "hard to say". That is honest, and it also means most
  forwards get no help.
- **Privacy.** The live look-up sends the claim text to Wikipedia and Google, only on a button press that says so. Nothing
  is stored server-side beyond local caches of fetched pages.
- **Language and script bias.** English is best served; Roman-script Punjabi translation is poor.
- **Dataset licensing.** The verdict components inherit the non-commercial terms of AVeriTeC.

## Caveats and recommendations

- Use it as an aid that points to sources, not as a verdict machine.
- Re-validate on your own claims before relying on it in a new setting; thresholds were chosen on dev data from specific
  distributions.
- Do not change the live rule (V2) or the frozen splits without a new pre-registered protocol and fresh claims.
- If you extend it, record choices made after seeing numbers as post hoc, as this project does.
