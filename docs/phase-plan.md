# Current phase and what is in scope

Pointer file. The reasoning lives in [build-plan.md](build-plan.md); this says
only where the project is right now, so a session can be oriented in ten
seconds without reading the whole plan.

**Update the "Current phase" line at the start of every session.**

> The running narrative — what was built, what was decided, why — lives in
> [project-log.md](project-log.md). This file is just the scope pointer.

## Current phase

**Phase 0 complete. AVeriTeC and X-CLAIM acquired and frozen. Phase 1 not started.**

The clock is **14 days**, and **Day 1 is the first day of Phase 1** — it has not
started, so the count has not started. Target machine: Intel i7-14700HX with an
**RTX 4050 laptop GPU, 6 GB VRAM**. No Colab. Every model choice is constrained by
that card; see `specs/SYSTEM_DESIGN.md` §10 for the GPU budget.

Out of scope until Phase 1 opens: **all model code**. Nothing in `src/` imports
torch, transformers, sentence-transformers or FAISS yet, and CI depends on that
staying true — the fast job installs the core lock only.

## What exists

| Piece | Where | State |
| --- | --- | --- |
| Eval harness | `src/eval/evaluate.py` | Works: classification + retrieval. 5 guardrails |
| Metrics | `src/eval/metrics.py` | Cross-checked against scikit-learn |
| Dumb baselines | `src/eval/baselines.py` | majority_class, stratified_random, random_rank |
| Results tables | `src/eval/report.py` | `make table` → `docs/results.md` |
| Leakage detection | `src/data/leakage.py` | 4 checks, proven against planted leaks |
| Dataset loaders | `src/data/loaders.py` | **Done** — AVeriTeC, X-CLAIM |
| Script detection | `src/data/script_id.py` | **Done** — per row, never from the lang label |
| Frozen splits | `data/splits/` | **Done** — averitec 2666/500/307, x_claim 5343/600/571 |
| Profiling | `scripts/profile_data.py` | **Done** — `make profile` → `docs/data-profile.md` |
| CI | `.github/workflows/ci.yml` | Green. `check` + `data` (proves splits reproduce from source) |
| Pipeline, API, UI | `src/pipeline/`, `app/` | **Not started** — Phase 1 |

## Next: Phase 1 — vertical slice, English only (Day 1)

AVeriTeC dev → BM25 over its knowledge store → off-the-shelf NLI for a 5-class
verdict → template explanation with source links → `POST /verify` → one plain HTML
page. Ugly, working, committed. Its numbers are the floor everything else beats.

Contracts and module layout are specified in `specs/SYSTEM_DESIGN.md` §4–5;
requirements in `specs/SRS.md`. Do not re-derive them here.

### Nothing is blocking. Cleared 21 Sep 2026

| Was blocking | State |
| --- | --- |
| AVeriTeC knowledge store | **Downloaded** — dev, 11.54 GB, `make kb`. 500 per-claim files, hashed, join to `dev.json` verified |
| CUDA torch | **Installed** — `2.9.1+cu128`, `cuda.is_available() == True` on the RTX 4050 |
| ML stack | **Installed** — transformers 5.17, sentence-transformers 6.1, faiss 1.15, FastAPI 0.141 |
| Transliteration not pinned | **Pinned** — `indic-transliteration` 2.3.82 as the baseline |

Day 1 can start on code.

### Open, not blocking

- **MultiClaim** — access requested on Zenodo, not yet granted. **If it is not
  approved by Day 5, swap Phases 4 and 5** and do evidence retrieval first.
- **IndicXlit spike, Day 2.** `ai4bharat-transliteration` depends on fairseq —
  confirmed from its PyPI metadata — which does not install cleanly on
  Windows + Python 3.11. The rule-based `indic-transliteration` is already
  pinned and working, so Phase 2 is not blocked either way. Timebox the spike to
  30 minutes and treat IndicXlit as an upgrade, measured against the baseline on
  Dakshina.
- **CheckThat! 2025 Task 2** — not started; needed for Phase 3.
- **Real VRAM is ~4.9 GiB, not 5.5 GB.** Windows reserves ~1 GiB of the 6 GiB
  for the desktop. NFR-3's ceiling is optimistic; see `environment.md`.
- **`hf.co`, not `huggingface.co`.** The long hostname is reset on this
  connection (0/12 in a measured test); the alias works. Applies to model
  downloads too.

## Phase order — 14 days

Day 1 is the first day of Phase 1.

| Phase | Days | What |
| --- | --- | --- |
| 0 | — | Harness and data. **Done.** |
| 1 | 1 | Vertical slice, English only |
| 2 | 2–3 | Language layer; the native vs romanized table |
| 3 | 4 | Front of pipeline: check-worthiness, span ID, normalization |
| 4 | 5–6 | Claim matching *(swaps with Phase 5 if MultiClaim is not approved by Day 5)* |
| 5 | 7–8 | Evidence retrieval and stance |
| 6 | 9–11 | Verdict aggregation, calibration, grounded generation |
| 7 | 12–14 | Demo, ablations, report. **Code freezes end of Day 12.** |

Days 13–14 are writing and demo polish only. Nothing new ships in them.

## The cut list, in order

Decided in advance so it is not decided in panic on Day 11.

1. Manipulation detection as a trained classifier -> zero-shot prompt + rules
2. Live search API -> static corpus, recency limitation reported honestly
3. Punjabi *generation* -> Punjabi retrieval and verdict, explanation in HI/EN
4. Seq2seq + attention summariser -> attention visualisation on the stance model

Never cut: the claim-matching fast path, abstention and calibration, the
romanized vs native comparison.

## Ask these three before every experiment

1. What is the current number for this component in `results/`?
2. What is the dumb baseline?
3. What would make this experiment **invalid**?

The third is the one that stops a leaked result from shipping.
