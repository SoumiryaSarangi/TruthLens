# Error analysis

**Written for:** the report's error-analysis section and its examiner.

**Status:** taxonomy and method fixed (2026-10-02) before any case sheet was
read; cases categorised after the test run (`docs/test-protocol.md`).

## Method

- Cases are drawn by `scripts/error_cases.py`: seeded (42), stratified by error
  type or language/script cell, into gitignored `reports/cases/` (they quote
  dataset text, which never enters the repository).
- **Ten real failures per language** (build plan), across the stages that see
  that language:
  - **English**: AVeriTeC verdict failures, dev and test.
  - **Hindi**: MultiClaim matching (native and romanized), romanized and native
    X-CLAIM spans, hand-typed language ID / transliteration, demo forwards.
  - **Punjabi**: the same stages; MultiClaim has 7 test posts, so Punjabi cases
    lean on X-CLAIM, the hand-typed set and the demo forwards.
- Each case gets ONE category from the fixed list below. A case that fits none
  is filed `other` with a note, and the list is not edited to absorb it — a
  growing taxonomy is how an analysis ends up confirming itself.
- **Counts that are reported come from the harness** (confusion matrices,
  per-cell scores). This document tallies only the sampled cases, and says so.

## The first question

The served-stance decision named it: **confident wrong refutations of TRUE
claims** — gold Supported, served Refuted, confidence in the High band (≥ 0.60).
On the demo forwards this happened to Modi as Gujarat CM, the Taj Mahal and the
Harmandir Sahib. All such cases on dev and test are listed in full, each with
the claim-only control's prediction beside it: if the control makes the same
error, the cause is the claim prior, not the evidence.

## Categories (fixed before reading)

| Code | Category | Means |
| --- | --- | --- |
| R | Retrieval miss | No gold / no relevant passage in what the stance model read |
| W | Wrong-claim evidence | Relevant-looking evidence about a DIFFERENT claim on the same entity (a fact-check title about another rumour, a disambiguation page) |
| P | Claim prior | The claim-only control makes the same error: the verdict came from the claim's wording, not the evidence |
| C | NEI / Conflicting confusion | Gold or prediction is NEI or Conflicting and the evidence is genuinely thin or mixed |
| L | Language layer | Wrong language ID or a transliteration error changed what later stages read |
| S | Span boundary | The claim span starts or ends in the wrong place (FR-7) |
| G | Gold ambiguity | The gold label or span is itself arguable |
| X | Extraction | A non-claim sentence was verified as a claim, or the claim was missed (served extractor) |
| other | — | Fits none; noted, not absorbed |

## Tie-break

Added at the first case that fitted two categories, before the Hindi and
Punjabi sheets were read: **P > R > W > L > S > C > X > G.**
- If the claim-only control makes the same error, the cause is the claim
  prior, whatever else is true.
- Failing that, a retrieval miss (no gold in the top 10) outranks what the
  model then did with the wrong evidence, and so on down the list.

A case's other plausible category is noted beside it, but the tally follows the
rule.

## Cases

Case sheets are in `reports/cases/`, which is gitignored because they quote
dataset text. Here, claims are quoted only for AVeriTeC (CC BY-NC, quoted for
analysis) and for our own demo forwards. MultiClaim posts are paraphrased.

### English: AVeriTeC test, served verdict (10 of 165 wrong)

| Case | Gold → predicted (conf) | Gold doc in top 10? | Control | Category |
| --- | --- | --- | --- | --- |
| 00134 "70% of Americans in poverty are white" | Refuted → Supported (0.43) | no | NEI | R |
| 00050 a Trump quotation | Refuted → Conflicting (0.45) | no | Refuted | R |
| 00141 Russian mercenaries in Syria "not in combat" | Refuted → NEI (0.33) | no | Conflicting | R |
| 00243 subpoenas vs bills passed | Supported → Conflicting (0.32) | yes, rank 1 | Supported | C: evidence found; Conflicting 0.32 edged out Supported 0.29 |
| 00290 Nigeria's anti-corruption progress | Supported → NEI (0.47) | yes, rank 6 | Supported | C (also G: "solid progress" is vague) |
| 00041 Madaraka Express passenger count | NEI → Supported (0.38) | yes, rank 8 | Supported | **P**: the control makes the same error |
| 00018 "Biden abandoned Scranton" | Conflicting → Refuted (0.34) | no | Conflicting | R (also G: a characterisation, not a fact) |
| 00249 a mayor's murder statistics | Supported → Refuted (0.41) | no | NEI | R |
| 00014 Kenyan road-building figures | Conflicting → Supported (0.43) | no | NEI | R |
| 00025 Klobuchar refugee pledge | NEI → Refuted (0.45) | no | Conflicting | R |

**Tally: R 7, C 2, P 1.**
- Seven of the ten wrong verdicts were reasoned over evidence that did not
  contain the answer. The harness says the same at scale: hybrid retrieval puts
  a gold document in the top 10 for 15.3% of test claims (Success@10
  0.1531 (run 3cd7a0719b5b)).
- **The confident wrong refutation of true claims does not occur on AVeriTeC
  test.** No true claim is refuted at confidence ≥ 0.60 (dev: 3 of 122). It is
  a demo-corpus failure (below).

### Hindi (10)

| Case | Stage | What went wrong | Category |
| --- | --- | --- | --- |
| hi:test:00260 | matching | A condolence post about a crime victim, matched to a fact-check on a different funeral video | R (also W) |
| hi:test:00476 | matching | A Devanagari post whose claim is in its video; the text is only a share request plus hashtags | R (also G) |
| hi:test:00732 | matching | An election-promise post, matched to a different fact-check about the same politicians | R (also W) |
| hi:test:00060 | matching | "Be careful if you eat grapes": the text states no specific claim | R (also G) |
| hi:test:00595 | matching | Top-1 is the same story (a dancing district officer) from another publisher; gold is at rank 3 | G: an unannotated equivalent |
| hi:test:00573 | matching | Top-1 is the same story (a mirrored injury photo); gold is at rank 3 | G: an unannotated equivalent |
| x_claim_romanized:hi:test:00098 | span, romanized | One name tagged instead of the slogan sentence | S |
| x_claim_romanized:hi:test:00026 | span, romanized | No span at all on a long post | S |
| x_claim_romanized:hi:test:00011 | span, romanized | The whole post tagged | S |
| x_claim_romanized:hi:test:00074 | span, romanized | No span at all (the claim is a quotation at the start) | S |

**Tally: R 4, S 4, G 2.** Two of the "failures" are correct matches that the
annotation doesn't list. This is exactly why MultiClaim's false-accept rate is
reported as an upper bound.

### Punjabi (10)

| Case | Stage | What went wrong | Category |
| --- | --- | --- | --- |
| pa:test:00001 | matching | A farmer-and-soldier-son photo story; top-1 is a fact-check of the same photos; gold is at rank 3 | G |
| pa:test:00002 | matching | A Hindi post filed as Punjabi (it has a Punjabi hashtag); the Hindi version of the right fact-check was top-1, but the English gold is beyond rank 10 | R (also G) |
| pa:test:00004 | matching | Banter with no claim in the text | R (also G) |
| pa:test:00006 | matching | Top-1 is a Bengali fact-check about a different politician's gesture; gold is at rank 4 | W |
| pa:test:00003 | matching | A vaccine-risk post; the gold fact-check is itself in Punjabi and was not retrieved; top-1 is in Portuguese | R |
| pa:test:00008 | matching | "Which state's police uniform is this?"; top-1 is an Albanian article on traffic rules | R |
| x_claim_romanized:pa:test:00063 | span, romanized | Claim shifted from the tribute sentence to the record sentence | S |
| x_claim_romanized:pa:test:00012 | span, romanized | Span starts too early | S |
| x_claim_romanized:pa:test:00072 | span, romanized | No span on a "beware, there is a gang in Bhopal" alarm forward | S |
| x_claim_romanized:pa:test:00094 | span, romanized | Span starts mid-sentence | S |

**Tally: R 4, S 4, G 1, W 1.**
- Eight of MultiClaim's nine Punjabi test posts fail at top-1.
- The pool holds 5 Punjabi fact-checks out of 78,077, so a Punjabi post
  matches cross-lingually or not at all.
- One of the misses is a Punjabi post whose own Punjabi fact-check exists in
  the pool.

### Romanized typing: the language layer (6 of the 15 hand-typed failures)

All six are **L**, from real hand-typed forwards (dev):
- **Read as English:** two code-mixed Hindi messages heavy with English
  ("Amazon lucky customer scheme… OTP verification", "CONGRATS!!! tum lucky
  winner ho"), and one Punjabi message.
- **Read as Punjabi:** a Hindi message with one Punjabi postposition ("24
  ghante ch").
- **Read as Hindi:** a Punjabi message.
- **Read as "other":** a Hindi message.

Every one is code-mixing, which a single language label per message cannot
represent.

### The demo forwards: true claims refuted with confidence

| Forward (truth: true) | Served | Claim-only control | Evidence shown | Category |
| --- | --- | --- | --- | --- |
| Narendra Modi Gujarat ke mukhyamantri rahe hain | Refuted 0.67 | Refuted 0.45 | fact-check titles about other Modi rumours | **P** (also W) |
| Taj Mahal Shah Jahan ne banwaya tha | Refuted 0.72 | Refuted 0.54 | a disambiguation page, and fact-checks about a replica and an AI image | **P** (also W) |
| ਹਰਿਮੰਦਰ ਸਾਹਿਬ ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਸਥਿਤ ਹੈ | Refuted 0.59 | Refuted 0.54 | three passages, **all labelled Supports** | **P** |

**All three are the claim prior.** The control, which never reads evidence,
refutes them too.
- **Where the prior comes from.** The model is trained on fact-checked claims,
  which are overwhelmingly false (Refuted is 57–61% of every AVeriTeC split).
  It learns that a forwarded "X did Y" is probably false, and the evidence
  doesn't move it enough.
- **The third row makes the served design's cost visible.** NLI labels the
  passages the user sees (all Supports), XLM-R decides the verdict (Refuted),
  and the card shows both.
- **Why only on free text.** On AVeriTeC test none of this appears at high
  confidence. On free text, the demo corpus supplies fact-check titles about
  *other* rumours on the same entity, and the failure appears.

**After the test run** (report §8a), the cause of the Taj Mahal row was traced
one step further: the transliterator had garbled the names (तज महल शह जहन), and
the claim was searched in Latin letters, so the Hindi Wikipedia corpus was never
searched in its own script. With lexicon-first transliteration and a
native-script query:
- **Modi** now abstains, leaning NEI.
- **The Taj Mahal** is still refuted, but at Medium confidence (0.57) rather
  than High (0.72).
- **The Harmandir Sahib** is unchanged: it is Gurmukhi input, so it is never
  transliterated, and its error is the prior alone.

## What the cases say

1. **Retrieval fails first, wherever it applies.** Seven of ten English verdict
   errors, and eight of twenty matching errors, had no correct document in the
   top 10.
2. **After retrieval comes the claim prior.** The system's confident mistakes
   on real forwards are the claim-only control's mistakes.
3. **Romanization shows up where it was measured cleanly:** span boundaries,
   and language ID on real typing. It does not show up as a matching penalty,
   because MultiClaim's "romanized" cell is mostly not romanized: of 53 test
   posts, 23 are Devanagari posts with Latin hashtags, 13 are mostly English,
   and 17 are romanized Hindi.
4. **The fixes these point at** are retrieval depth and a correction for the
   claim prior, not a better stance model.
