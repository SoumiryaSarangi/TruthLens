# Better English for romanized claims: translation route variants (written 2026-10-06 BEFORE any variant is run or any translation measured)

## Why
Every live verdict on a Hindi or Punjabi claim is judged on its English translation (route A, `docs/live-fever-protocol-2.md`). A romanized claim ("Cinnamon stick se steam inhale karne par lungs detox nahi hote") is first turned into Devanagari by a **lexicon transliteration**
and then translated by NLLB-200 distilled 600M. Read from the stored runs: the English the models received was often garbled ("They don't give lounges if they stream from a cinnamon stick."; "Drinking lemons and worms can't keep Novel Choronvirus from dying."), and 6 of 49
translated negations lost their negation. Romanized input is the project's primary use case, so the quality of this one step bounds everything after it. This protocol measures it and tests the smallest changes.

## Frozen
The live rule V2, the title-grounding gate, every threshold, the polarity guard (now on), the NLI models. Only the string handed to them as "the English claim" may change.

## Variants (fixed now; no other variant is tried on the same data)
- **V0 (served):** lexicon transliteration to Devanagari/Gurmukhi, then NLLB-600M (`hin_Deva` / `pan_Guru` to English, beam 4).
- **V1:** no transliteration: the Latin-script sentence is passed to NLLB as it was typed, tagged as the Hindi or Punjabi source language.
- **V2 (pick):** both V0 and V1 candidates are produced, and the one whose BGE-M3 embedding is closer to the ORIGINAL romanized sentence is used (BGE-M3 is already loaded for the live path; no gold label is involved).

## Development set and measure (selects a variant; touches no verdict)
RC-D (`data/private/real_forwards_triplets.csv`): 40 claims each written in English and in a romanized rendering (Roman Hindi or Roman Punjabi), minus the 6 excluded rows. For every romanized rendering the English rendering of the SAME claim is the reference.
- **Primary:** mean BGE-M3 cosine between the candidate English and the reference English.
- **Secondary:** chrF against the reference; and **negation preservation**: among references that contain a negation word, the share of candidates that also contain one.
- **Selection rule:** a variant replaces V0 only if its primary measure is higher by at least 0.03 (absolute) with a cluster-bootstrap (cluster = claim, 1000 resamples, seed 42) 95% interval for the paired difference above zero, AND its negation preservation is not lower than V0's by more than 2 points.
  If both V1 and V2 qualify, the one with the higher primary measure is taken. **If none qualifies, the protocol ends here and V0 stays.** The measure is a proxy for the downstream effect, so passing it is not adoption.

## Final test (paired, through the served pipeline; fixed now)
The sentences typed in Roman Hindi or Roman Punjabi in RC-B, RC-E, RC-F and RC-G (these sets were used for other decisions, but never to choose a translation variant, so they are held out for this one) are run twice through the same server and config (guard on), once with the selected variant
(`live_translate_variant` config key, off by default) and once with V0, in one session so nothing else differs. Paired comparison on decidable gold-T/F sentences:
1. **Right answers:** the variant shows at least 10% more correct verdicts than V0, and the paired difference is reported with a bootstrap interval (cluster = source family where a set has one, else the sentence).
2. **Not more wrong:** wrong shown verdicts do not rise, and false Supported does not rise.
3. **Precision on shown decidable claims stays at least 0.85 with Wilson lower bound at least 0.80** (the bars of `docs/real-claims-protocol.md`).
If any fails the variant is not shipped and the failure is reported with the same weight. If it passes, the key is turned on, tested, and recorded; the owner restarts the server.

## Limits stated now
BGE-M3 cosine is a proxy (a paraphrase scores high even if one fact changed); the reference is the owner's own English rendering; the Punjabi share of the development set is small (about 18 renderings); the final test reuses sets already used for other decisions; NLLB-600M is the only translator that fits beside the NLI models on the GPU, so a larger translator is out of scope.

## Result of the development step (2026-10-06, run `366771a6687f`, `results/366771a6687f.json`): NO VARIANT QUALIFIES; V0 stays and the protocol ends here
36 clusters, 53 romanized renderings (36 Hindi, 17 Punjabi) of RC-D, the claim span extracted as the served pipeline does, the English rendering of the same claim as the reference.

| route | cosine to the reference | chrF | difference vs V0 (cluster bootstrap 95%) | qualifies |
| --- | --- | --- | --- | --- |
| V0 (served) | 0.708 | 0.298 | | |
| V1 (no transliteration) | 0.686 | 0.258 | -0.022 (-0.054 to -0.004) | no: worse |
| V2 (pick by closeness to the original) | 0.685 | 0.258 | -0.023 (-0.055 to -0.005) | no: worse |

By language, V0 is 0.734 (Hindi) and 0.655 (Punjabi); V1 is slightly better on Punjabi (0.666) but not significantly and worse on Hindi. **The selection rule needed a rise of at least 0.03 with an interval above zero; both variants fall, with intervals below zero. The protocol ends and V0 stays.**
- **V2's pick rule was badly biased:** it chose the V1 candidate for 98% of the items, because the Latin-script input candidate is closer to the Latin-script original in BGE-M3 space whatever its quality. That is a design fault of the rule, found from this result; it is not retried on the same data.
- **The negation figures in the output (V0 0.40, V1 0.00, "references with negation" 20) are NOT a valid measurement and are not reported as a finding:** read afterwards, the references (the English renderings of RC-D) carry templated wrapper text ("Not sure if true...", "I really can't tell"), which the negation check counted, and the claim span extraction does not strip it. The cosine and chrF comparisons contain the same wrapper text for every variant, so the ranking is unaffected; the negation criterion would also not have rescued a variant (it can only block one).
- **A qualitative reading (post hoc, not a measure):** V0 often yields poor English ("Is it necessary to enjoy drinking to save money?" for a UPI PIN claim; "Bear and cold drink" for ORS), most visibly in Roman Punjabi. A better translator is the obvious lever, but the only candidate that fits is NLLB-600M: the 1.3B model needs about 2.6 GiB of GPU memory while translating against about 0.4 GiB of headroom,
  and on the CPU it would add tens of seconds per claim. That is recorded as a hardware limit, not tested.
