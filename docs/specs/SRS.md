# TruthLens — Software Requirements Specification

| | |
| --- | --- |
| **Status** | v1.0 · 21 Sep 2026 |
| **Owns** | Numbered, testable requirements and how each one is verified |
| **Does not own** | Why a requirement exists → `PRD.md` · how it is built → `SYSTEM_DESIGN.md` |
| **Structure** | Loosely follows IEEE 830: introduction, overall description, specific requirements |

Every requirement has an ID, a priority (P0 never cut, P1, P2 — see `PRD.md` §5) and a **verification method**: `test` (pytest), `eval` (an eval config through `make eval`), `demo` (shown in the UI), or `review` (documented and inspected). A requirement with no way to verify it is not a requirement.

---

## 1. Introduction

### 1.1 Purpose

Specify what TruthLens must do and how well, precisely enough that each requirement can be checked by a test, an evaluation run, or a demonstration.

### 1.2 Scope

TruthLens accepts a text forward in English, Hindi or Punjabi, in native or Roman script, and returns a verdict about the factual claim or claims in it, with evidence, a calibrated confidence, and an explanation. It runs locally on a single laptop. See `PRD.md` §3 for non-goals.

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| **Forward** | The raw input text, as a user would paste it |
| **Claim** | A single checkable factual statement extracted from a forward |
| **Check-worthy** | Contains at least one verifiable factual claim |
| **Verdict** | One of the 5 classes in `src/data/labels.py` → `VERDICT_5CLASS`: `Supported`, `Refuted`, `Conflicting`, `NEI`, `NotAClaim` |
| **NEI** | Not Enough Evidence — the *evidence* is insufficient |
| **Abstain** | The *system* is not confident enough in its own verdict. Separate from NEI: a response can carry any verdict and still be marked abstained |
| **Native script** | Devanagari (`deva`) for Hindi, Gurmukhi (`guru`) for Punjabi, Latin (`latn`) for English |
| **Romanized** | Hindi or Punjabi written in Latin script |
| **Fast path** | Resolution via a matched, previously published fact-check |
| **Evidence path** | Resolution via retrieval, stance and aggregation |
| **uid** | The join key in every split and predictions file, e.g. `x_claim:hi:dev:00042` |

## 2. Overall description

### 2.1 Product perspective

A standalone local system: a Python pipeline in `src/`, served by FastAPI in `app/`, with an offline evaluation harness already in place in `src/eval/`. The harness exists before any model does, and every model stage must be evaluable through it.

### 2.2 Constraints

| ID | Constraint |
| --- | --- |
| C-1 | Target machine: Intel i7-14700HX, NVIDIA RTX 4050 laptop GPU with **6 GB VRAM**, Windows 11 |
| C-2 | Python 3.11 via uv. System Python 3.13 is not used |
| C-3 | 14-day build. Code freezes at the end of Day 12 |
| C-4 | AVeriTeC is CC BY-NC 4.0; MultiClaim is access-restricted and may not be redistributed. The repo commits ID manifests, never dataset text |
| C-5 | Must work fully offline once models and corpora are downloaded. Live search, if built at all, is optional |
| C-6 | Solo developer, implemented largely through Claude Code |

### 2.3 Assumptions

- ~~MultiClaim access is granted during the build.~~ **Granted 22 Sep 2026 and ingested**, so FR-8 is no longer at risk. Punjabi is: the corpus holds 91 Punjabi posts in total, 7 of them in dev.
- Hindi and Punjabi explanation quality is judged by a native speaker at least once before the demo.

## 3. Functional requirements

### 3.1 Input and language layer

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-1 | P0 | Accept UTF-8 text of 1–4000 characters. Reject empty or whitespace-only input with a validation error, never a verdict | test |
| FR-2 | P0 | Strip forward artefacts ("Forwarded many times", header lines, emoji runs) for processing, while keeping the original text in the response | test |
| FR-3 | P0 | Identify language as `en`, `hi`, `pa` or `other`. `other` returns a clear unsupported-language response, not a verdict | test, eval |
| FR-4 | P0 | Detect script per input as `deva`, `guru` or `latn` using `src/data/script_id.detect_script`, and report how code-mixed the input is via `script_purity` (1.0 = single script). There is no `mixed` script value — see `SYSTEM_DESIGN.md` §4. Never infer script from the language label | test |
| FR-5 | P0 | Transliterate romanized Hindi and Punjabi into native script for downstream stages. Keep the original, and record in the response that transliteration happened | test, eval |

### 3.2 Claim understanding

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-6 | P0 | Classify check-worthiness. A non-check-worthy forward short-circuits to `NotAClaim`, with no retrieval run | test, eval |
| FR-7 | P0 | Extract claim spans and normalize each into a standalone claim. At most **3** claims per forward are verified; the rest are listed as not checked | test, eval |

### 3.3 Verification

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-8 | P0 | **Claim matching.** Retrieve the top-k previously published fact-checks for each claim, across languages. If the best match scores at or above threshold τ_match, resolve on the fast path using that fact-check's verdict | eval |
| FR-9 | P0 | **Evidence retrieval.** For claims not resolved by FR-8, retrieve top-k evidence passages with hybrid BM25 + dense scoring | eval |
| FR-10 | P0 | **Stance.** Classify each retrieved passage as `Supports`, `Refutes` or `Neutral` toward the claim (`STANCE_3CLASS`) | eval |
| FR-11 | P0 | **Aggregation.** Combine stances into one 5-class verdict with a confidence in [0, 1]. Strong support and strong refutation together yield `Conflicting` | eval |
| FR-12 | P0 | **No evidence, no verdict.** Zero passages retrieved, or none above the relevance floor, yields `NEI` with `abstained = true` | test |
| FR-13 | P0 | **Calibration.** Confidence is calibrated on dev (temperature scaling at minimum), and ECE is reported before and after | eval |
| FR-14 | P0 | **Abstention.** Confidence below threshold τ_abstain sets `abstained = true`. τ_abstain is selected on dev, never on test, and recorded in the served config | eval, test |

### 3.4 Explanation

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-15 | P0 | Generate an explanation grounded in the retrieved evidence, citing passage IDs inline | eval, demo |
| FR-16 | P0 | Check each explanation with NLI against its cited evidence. An explanation that fails is **replaced** by the template explanation, and the replacement is recorded | test, eval |
| FR-17 | P1 | Explanation language matches the input language. Punjabi may fall back to Hindi or English (cut list item 3); the fallback is shown to the user | demo |
| FR-18 | P0 | A template explanation always exists and is used whenever generation is unavailable, times out, or fails FR-16 | test |

### 3.5 Secondary analysis

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-19 | P2 | Flag manipulation techniques using the SemEval-2023 Task 3 label inventory, via zero-shot plus rules. Flags never change the verdict | demo |

### 3.6 Interface

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-20 | P0 | `POST /verify` accepts the request schema and returns the response schema in `SYSTEM_DESIGN.md` §8 | test |
| FR-21 | P0 | `GET /health` reports whether each stage's model is loaded. `GET /version` reports git SHA, served pipeline config hash, τ values, and the `confidence_bands` cut points the UI needs (`UI_UX.md` §7 forbids hard-coding them in JavaScript, so the API must supply them) | test |
| FR-22 | P0 | Every response carries a stage trace: what each stage produced and how long it took. The UI's evidence trail is rendered from it | test |
| FR-23 | P0 | A WhatsApp-styled web UI, served at `/`, implements the states in `UI_UX.md` | demo |

### 3.7 Evaluation

| ID | Pri | Requirement | Verify |
| --- | --- | --- | --- |
| FR-24 | P0 | Every model stage can run in batch over a frozen split and emit a predictions JSONL that `make eval` accepts. The served pipeline and the evaluated pipeline are the **same code** | test |
| FR-25 | P0 | Every stage has a registered dumb baseline evaluated in the same table | review |
| FR-26 | P0 | Romanized evaluation sets exist for Hindi and Punjabi: transliterated X-CLAIM test, plus ~100 hand-typed forwards, reported separately | review, eval |
| FR-27 | P1 | Cross-lingual t-SNE figure from LaBSE embeddings of parallel claims | review |

## 4. Non-functional requirements

| ID | Category | Requirement | Verify |
| --- | --- | --- | --- |
| NFR-1 | Performance | `POST /verify` p95 ≤ **10 s** warm on the target machine with GPU, for a forward under 1000 characters. Fast-path responses p95 ≤ 3 s | test (timed) |
| NFR-2 | Performance | Cold start, with all models loaded, ≤ 90 s | review |
| NFR-3 | Resources | Inference peak VRAM ≤ **5.5 GB**, leaving headroom on the 6 GB card | review |
| NFR-4 | Resources | Training runs one model at a time and never alongside the API server | review |
| NFR-5 | Reproducibility | Seed 42 everywhere; every result carries config hash, git SHA, env and torch build. Existing Phase 0 guarantees are not weakened | test |
| NFR-6 | Integrity | Frozen splits, `SPLITS.lock`, the leakage tests and the test-split guard stay in force. No requirement here may be met by bypassing them | test |
| NFR-7 | Degradation | A failing stage degrades rather than crashing the request: dense → BM25, generation → template, matcher down → evidence path only. The degradation appears in the trace | test |
| NFR-8 | Privacy | Input text is not logged by default and never leaves the machine unless live search is explicitly enabled | review |
| NFR-9 | Safety scope | Opinions, predictions and value judgements route to `NotAClaim`. Every verdict shows its sources | eval, demo |
| NFR-10 | Maintainability | `make lint` and `make test` pass on every commit to `main`; CI is green | test |
| NFR-11 | Portability | Runs on Windows 11 locally and Linux in CI. Paths via `pathlib`; UTF-8 forced for console output | test |
| NFR-12 | Accessibility | UI meets WCAG AA contrast, is fully keyboard operable, and never uses colour alone to convey a verdict | review |

## 5. Data requirements

| Dataset | Used for | Licence / access | State |
| --- | --- | --- | --- |
| AVeriTeC | Verdict, evidence retrieval | CC BY-NC 4.0 | Claims in `data/splits/averitec/` · knowledge store not yet downloaded |
| X-CLAIM | Claim spans, EN/HI/PA | Research release | In `data/splits/x_claim/` |
| CheckThat! 2025 Task 2 | Claim normalization, EN/HI/PA | Public GitLab repo, no registration | Downloaded 2026-09-24 |
| MultiClaim v2 | Claim matching | Restricted, not redistributable | **Acquired.** ID manifests in `data/splits/multiclaim/`; CSVs stay in gitignored `data/raw/` |
| SemEval-2023 Task 3 | Manipulation labels (P2) | Registration | Not started |
| Dakshina | Transliteration evaluation | Open | Not started |

## 6. Traceability

| Requirement | Phase | Where verified |
| --- | --- | --- |
| FR-1, FR-2, FR-20–22 | 1 | `tests/test_api.py`, `tests/test_contracts.py` |
| FR-9, FR-11, FR-12, FR-18, FR-24 | 1 (baseline versions) | `configs/p1_*` evals |
| FR-3, FR-4, FR-5, FR-26, FR-27 | 2 | `configs/p2_*` evals, romanized table |
| FR-6, FR-7 | 3 | `configs/p3_*` evals |
| FR-8 | 4 | `configs/p4_*` evals |
| FR-9, FR-10 (model versions) | 5 | `configs/p5_*` evals |
| FR-11–17 (model versions) | 6 | `configs/p6_*` evals, abstention curve |
| FR-19, FR-23, NFR-1, NFR-12 | 7 | demo script in `UI_UX.md` §11 |

## 7. Acceptance

The release is accepted when every P0 requirement is verified by its stated method, every P1 or P2 requirement that was cut is recorded as cut in `docs/project-log.md` with the reason, and `make test`, `make lint` and `make leakage` pass on a clean clone.
