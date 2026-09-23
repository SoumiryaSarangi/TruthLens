# Current phase and what is in scope

Pointer file. The reasoning lives in [build-plan.md](build-plan.md); this says
only where the project is right now, so a session can be oriented in ten
seconds without reading the whole plan.

**Update the "Current phase" line at the start of every session.**

> The running narrative — what was built, what was decided, why — lives in
> [project-log.md](project-log.md). This file is just the scope pointer.

## Current phase

**Phase 1 complete. Phase 2 (Days 2-3) not started, nothing blocking it.**

The clock is **14 days**. **Day 1 is done** — Phase 1 shipped the vertical
slice with real numbers. Day 2 opens Phase 2. Code freezes at the end of Day 12.

Target machine: Intel i7-14700HX with an **RTX 4050 laptop GPU, 6 GB VRAM**
(~4.9 GiB usable — Windows holds the rest). No Colab. Every model choice is
constrained by that card; see `specs/SYSTEM_DESIGN.md` §10.

**CI runs the core lock, which has no torch.** Nothing under `src/` may import
a model library at module scope; `tests/test_contracts.py` enforces it
statically. Stages import their models lazily inside methods.

## What exists

| Piece | Where | State |
| --- | --- | --- |
| Eval harness | `src/eval/evaluate.py` | 5 guardrails; classification + retrieval |
| Metrics | `src/eval/metrics.py` | Cross-checked against scikit-learn |
| Dumb baselines | `src/eval/baselines.py` | majority_class, stratified_random, random_rank |
| Leakage detection | `src/data/leakage.py` | 4 checks, proven against planted leaks |
| Dataset loaders | `src/data/loaders.py` | **AVeriTeC, X-CLAIM, MultiClaim** |
| Script detection | `src/data/script_id.py` | Per row, never from the lang label |
| Frozen splits | `data/splits/` | averitec 2666/500/307 · x_claim 5343/600/571 · multiclaim 25137/3153/3156 |
| Knowledge store | `data/raw/averitec_kb/` + cache | dev, 11.54 GB zip; per-claim cache in `data/interim/` |
| **Pipeline** | `src/pipeline/` | **Done** — contracts, registry, orchestrator, batch |
| **Stage baselines** | `src/{preprocess,claims,matching,retrieval,stance,generation,faithfulness}/` | **Done** — 8 impls |
| **API + UI** | `app/` | **Done** — `/verify`, `/health`, `/version`, plain page |
| Tests | `tests/` | 204 passing, 1 skipped, 1 gpu-deselected |
| CI | `.github/workflows/ci.yml` | Green — `check` + `data` (splits reproduce from source) |

## Phase 1 results — the floor everything must beat

| Component | Score | Baseline |
| --- | --- | --- |
| Retrieval Recall@10 | **0.0947** | 0.0121 (seeded random over the same pools) |
| Retrieval Success@10 | 0.1580 | 0.0240 |
| Verdict macro-F1 | **0.2147** | 0.1516 (majority_class) |
| Verdict accuracy | 0.3600 | 0.6100 (majority_class **wins** — read macro-F1) |

**Retrieval is the bottleneck.** Five claims in six have no gold document in the
top 10, so the stance model mostly reads irrelevant text. Improving the
aggregator before retrieval is tuning against noise.

## Next: Phase 2 — the language layer (Days 2-3) · Units I & II

fastText language ID, IndicXlit transliteration, code-mix normalisation, the
romanized eval sets, the embedding comparison (TF-IDF → Word2Vec → MuRIL →
LaBSE → BGE-M3), and the t-SNE plot. **Deliverable: the native vs romanized
table** — Units I and II of the report *and* the research contribution.

Script detection already exists and is reused, not rebuilt.

**The retrieval task to score the embedding comparison on now exists:**
MultiClaim, 3,153 dev / 3,156 test queries across en/hi/pa. Before it landed
there was none — AVeriTeC is English-only and X-CLAIM has no relevance
judgements. That was Phase 2's hardest blocker.

**Day 2 opens with the IndicXlit install spike, timeboxed to 30 minutes.**
`ai4bharat-transliteration` depends on fairseq, which does not install cleanly
on Windows + Python 3.11 — confirmed from its PyPI metadata, not assumed.
`indic-transliteration` 2.3.82 is already pinned and working, so Phase 2 is not
blocked either way; IndicXlit is an upgrade to measure against it on Dakshina.

### Still to download for Phase 2

Dakshina (2.01 GB), fastText `lid.176`, and the embedding models (BGE-M3, LaBSE,
MuRIL, ~7.6 GB). Hub connectivity here is intermittent — roughly half of
requests fail — so use something that resumes and do not restart from zero.

### Needs a human — I cannot do these

- **~100 hand-typed romanized forwards (FR-26, P0).** Cannot be automated and
  cannot be substituted: MultiClaim's 501 naturally romanized Hindi posts are
  public posts, not the messy personal typing the contribution is about. Brief
  for collectors is `collection-brief.md` — forward it as-is. Scheduled in
  Phase 2 but **reported separately from the synthetic set**, so Phase 2 is not
  blocked; the real deadline is **Day 11**, before the final tables.
  Punjabi is the priority: every other dataset here is thin on it.
- **Native-speaker review of `app/static/i18n/{hi,pa}.json`** before any demo.
  Those strings are unverified placeholders and are marked as such in the files.

### Open, not blocking

- ~~MultiClaim access~~ **GRANTED and ingested.** 25,137 / 3,153 / 3,156
  train/dev/test. The Phase 4-5 swap rule is moot. It also gives Phase 2 the
  multilingual retrieval task the embedding comparison needs.
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
