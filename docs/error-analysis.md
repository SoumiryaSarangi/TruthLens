# Error analysis

**Written for:** the report's error-analysis section and its examiner.

**Status:** taxonomy and method fixed (2026-10-02), BEFORE any case sheet was
read. Cases are filled in after the test run (`docs/test-protocol.md`).

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

## Cases

*(filled in after the test run)*
