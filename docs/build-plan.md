# TruthLens — Build Plan

Multilingual claim verification for forwarded misinformation (EN / HI / PA), including Romanized input. CSE472 — Deep Learning for NLP.

2026-09-19 · @Someone

> **Historical document.** This is the original rationale, kept because the
> reasoning behind each decision is still the reasoning. Where it disagrees with
> `docs/specs/` it is superseded; where it disagrees with the code, the code wins.
> Phase timings and the Phase 6 model choice below have been updated for the
> 14-day plan. Everything else is left as written on 19 Sep 2026, including the
> embedded copy of `CLAUDE.md` and the session starter prompts, which describe an
> earlier 4-class verdict scheme. The live files are the source of truth.

## Decisions locked

Settled by research on 19 Sep 2026. Each carries its reason so it doesn't get re-opened mid-semester. If one changes, note why here rather than silently swapping it.

| Area | Decision | Why |
| --- | --- | --- |
| Verification backbone | **AVeriTeC**, not FEVER | Real claims from 50 fact-checking orgs; 4-class labels (Supported / Refuted / Conflicting / NEI) almost exactly match our output scheme; ships QA-decomposition annotations and an offline knowledge store of \~1000 web articles per claim. FEVER is synthetic Wikipedia claims and won't transfer to forwards. Keep FEVER only as warm-start for the stance model. |
| Claim-matching data | **MultiClaim / SemEval-2025 Task 7**, no scraping | 206k professional fact-checks in 39 languages, 28k posts, 31k linked pairs. Removes the ToS and robots.txt risk entirely and gives a published leaderboard to compare against. AMC-16K is the curated 16k-pair subset if the full set is too heavy. |
| Claim span, EN/HI/PA | **X-CLAIM** | Exactly our three languages, real social posts. Train/dev/test: EN 3891/400/371, HI 1193/100/100, PA 346/100/100. Baseline code released. |
| Claim normalization | **CheckThat! 2025 Task 2**, not 2026 | The 2025 monolingual track includes Hindi and Punjabi; HI has 1081 train. The 2026 edition narrowed to Arabic, English, German, French and Spanish and is useless to us. |
| Manipulation techniques | **SemEval-2023 Task 3 subtask 3** label set | Established 23-technique inventory rather than invented labels. HI and PA become surprise languages, which is a free zero-shot cross-lingual transfer experiment. Winning system was XLM-R-large trained jointly with separately calibrated thresholds. |
| Retrieval model | **BGE-M3**, fallback multilingual-E5-large | LaBSE is a translation-ranking model, not a retriever: it scored 0.188 average nDCG@10 on BEIR, below every dedicated retrieval model. BGE-M3 leads 8 of 13 Indian languages on IndicMSMarco and beat LaBSE on the SemEval-2025 claim-retrieval setting. |
| LaBSE's actual role | **t-SNE cross-lingual plot only** | It genuinely excels at bitext alignment. That's the demo visual, not the retrieval engine. |
| Indic baseline | **MuRIL**, kept in the Unit II comparison | Gives a three-way embedding comparison (MuRIL / LaBSE / BGE-M3) instead of one arbitrary pick. |
| Transliteration | **IndicXlit** plus a context pass | \~11M params, 21 Indic languages, trained on Aksharantar (26M word pairs). It's word-level, which is the weakness: pair it with fastText or HingBERT language ID and an n-gram LM or HMM pass for context. Dakshina is the evaluation benchmark. |

### The realistic accuracy target

Published frameworks on AVeriTeC report roughly **47-50% accuracy**. Put that number on page one of the report. It turns "your accuracy is low" into "your accuracy is competitive with published state of the art", which is the difference between a defensive viva and a confident one.

### What the research contribution actually is

Not "romanized input is hard" — that's known. A documented finding already shows strong retrievers like BGE-M3 degrade badly on romanized queries, fixable via translate-train, mixing native and romanized text during training.

The contribution is **quantifying the romanization penalty across the full verification pipeline in Hindi and Punjabi, and identifying where in the pipeline it is cheapest to fix.**

No romanized EN/HI/PA verification test set exists, so building one is part of the work:

- Transliterate X-CLAIM's HI and PA test sets into Roman script — synthetic, clean
- Hand-type \~100 forwards naturally, with friends — real, messy
- Report both separately, and state plainly that synthetic romanization is easier than real typing

## Scope and the cut list

The original pitch has nine pipeline stages, six syllabus units and five standout features. That is three papers of work. Solo, in one semester, most of it would end up half-finished.

The fix is not less ambition. It is ordering the work so there is always a working system, and so cuts land on depth rather than breadth.

**Build one thin vertical slice end-to-end first, then thicken it.** Building stage 1 to stage 9 in order means week 12 arrives with six beautiful components and no demo. Building an ugly working pipeline by week 2 means everything after is an upgrade to something that already runs, and the project can be presented at any point from then on.

### Pre-committed cut list

Decided now, so the decision isn't made in panic at week 11. Cut strictly in this order.

| Order | What goes | Fallback |
| --- | --- | --- |
| 1 | Manipulation detection as a trained classifier | Zero-shot prompt plus a rule list over the 23 SemEval labels |
| 2 | Live search API | Static corpus only; report the recency limitation honestly |
| 3 | Punjabi *generation* | Punjabi retrieval and verdict, explanation in Hindi or English |
| 4 | Seq2seq + attention verdict summariser (Unit IV) | Attention visualisation on the stance model instead |

### Never cut

These three are what make the project distinctive. Everything else is replaceable.

- The claim-matching fast path — mirrors how real fact-checkers work, and will be the best-performing component
- Abstention and calibration — the "system that knows when it doesn't know" story
- The romanized vs native comparison — the actual research contribution

## Phase 0 — harness before models (3 days)

Train nothing this week. The dominant failure mode when building ML with an agent is not broken code — it is **plausible code that runs, produces numbers, and is silently wrong**. A leaked split, a metric averaged the wrong way, a test set touched during model selection. Claude Code will happily write a model that trains and prints 0.94 F1, and without a fixed harness there is no way to know that number is a lie.

This is not paranoia. The DS@GT team working on CheckThat! 2025 found substantial claim overlap, to the point of duplication, across the train, dev and test sets. Leakage is real in this exact data.

### Checklist

- [ ] Repo skeleton, pinned `requirements.txt`, Python 3.11
- [ ] Seeds fixed at 42 across numpy, torch, random, transformers — set in one place, imported everywhere
- [ ] Dataset loaders for AVeriTeC, X-CLAIM, CheckThat! 2025 T2, MultiClaim, returning one common schema
- [ ] Profiling script: per-language, per-split counts printed and committed to `docs/data-profile.md`
- [ ] **Frozen splits committed to git as `.jsonl` in `data/splits/`** — never regenerated after this
- [ ] `src/eval/evaluate.py` — takes a predictions JSONL and a config YAML, emits a metrics JSON
- [ ] `tests/test_no_leakage.py` — asserts zero claim-ID overlap between train, dev and test
- [ ] `results/` directory, one `{config_hash}.json` per run, committed
- [ ] `Makefile` with `eval`, `test`, `lint`, `leakage` targets
- [ ] `CLAUDE.md` at root plus subdirectory files for `data/` and `src/retrieval/`
- [ ] `.claude/settings.json` with safe commands pre-allowed
- [ ] First commit, pushed

### The three questions before every experiment

Pin these in CLAUDE.md and ask them at the start of every session from here on:

1. What is the current number for this component in `results/`?
2. What is the dumb baseline?
3. What would make this experiment **invalid**?

The third one is the important one. It is what stops a leaked result from shipping.

## Phases 1-7

**14 days, Day 1 = the first day of Phase 1.** Target machine: Intel i7-14700HX with an RTX 4050 laptop GPU, 6 GB VRAM. No Colab, so every model has to fit that card and training is one job at a time — see `specs/SYSTEM_DESIGN.md` §10 for the budget.

**If MultiClaim is not approved by Day 5, swap Phases 4 and 5**: do evidence retrieval and stance first and pick up claim matching when access lands. The fast path is never cut, only reordered.

### Phase 1 — vertical slice, English only (Day 1)

AVeriTeC dev subset → BM25 over its knowledge store → an off-the-shelf NLI model for a 5-class verdict → template-string explanation with source links → FastAPI `POST /verify` → one HTML page.

**Deliverable:** paste an English claim, get a verdict and three source links. Ugly. Working. Committed.

This is the insurance policy for the whole semester. Its numbers are the floor everything else must beat.

### Phase 2 — the language layer (Days 2-3) · Units I & II

- fastText language ID → script detection → IndicXlit transliteration → code-mix normalization → emoji and forward-artifact stripping
- Build the romanized eval sets: transliterated X-CLAIM HI/PA plus \~100 hand-typed forwards
- Embedding comparison scored on retrieval: TF-IDF → Word2Vec → MuRIL → LaBSE → BGE-M3
- The t-SNE plot: the same claim in EN, HI and PA landing in one region

**Deliverable:** the native vs romanized performance table. This is Units I and II of the report *and* the research contribution. Get it done early so there is time to iterate on it.

### Phase 3 — front of pipeline (Day 4) · Unit V

Check-worthiness filter, claim span identification on X-CLAIM, normalization on CheckThat! 2025 T2. Fine-tuned XLM-R with joint multilingual training, plus monolingual and zero-shot baselines for the ablation table. The "not a factual claim" class lives here.

X-CLAIM's own paper found joint multilingual training beats zero-shot transfer and beats training on English-translated data. Replicate that as a deliberate ablation rather than rediscovering it by accident.

### Phase 4 — claim matching track (Days 5-6)

MultiClaim / SemEval-2025 T7. Report Recall@k, MRR and Success@10, **split by language and by script**. Evaluate retrieval on its own before anything touches generation.

This will be the best-performing component and it is the architectural idea that sets the project apart. Lead with it in the demo.

### Phase 5 — evidence retrieval and stance (Days 7-8) · Unit III

Hybrid BM25 plus dense retrieval over Wikipedia EN/HI/PA and live search. BiLSTM stance detector as the Unit III baseline, versus fine-tuned XLM-R. Retrieval metrics reported separately from generation metrics.

### Phase 6 — verdict aggregation and grounded generation (Days 9-11) · Units IV & VI

Grounded explanation generation with citations, decoding-strategy comparison, NLI-based faithfulness scoring, calibration curve, abstention threshold sweep.

**Generator: IndicBART. Decided, not "mT5 or IndicBART".** Two reasons, in order:

1. **It fits.** 244M params, ~0.5 GB in fp16, on top of ~2.3 GB of other resident weights inside a 6 GB card with a 5.5 GB ceiling (NFR-3). mT5-base is 580M and mT5-small trades away the fluency that is the whole point of generating rather than templating. IndicBART is also pretrained on Indic languages, which is what the explanations are in.
2. **It is the right shape for the syllabus.** Unit IV wants seq2seq with attention. IndicBART is an encoder-decoder with cross-attention over the evidence, so the attention visualisation is over the actual evidence passages — the figure means something. A decoder-only model would satisfy the task but not the unit.

**Considered and not adopted: a modern small instruction-tuned model** — Qwen2.5-3B via QLoRA, or similar. It would almost certainly produce more fluent Hindi explanations than IndicBART, and on a 4-bit quantised load it would physically fit. It was rejected **to protect the 14-day timeline**, not on quality: a new quantisation and adapter stack on day 9 of 14 is the kind of thing that eats two days and returns a model that generates beautifully and cites nothing. IndicBART is the known quantity.

**If Days 9-11 have slack, spend it on a prompted-LLM comparison, not on mT5-small.** One table — IndicBART vs a prompted instruction-tuned model on the same claims, scored on the same NLI faithfulness metric — is a far more interesting result than a second small seq2seq baseline, and it answers the obvious viva question ("why not just prompt an LLM?") with a number instead of an opinion.

**The abstention curve is the headline result.** Accuracy at 100% coverage will look mediocre. Accuracy at 60% coverage, with the system declining the rest, looks excellent — and it is the honest, deployable framing.

### Phase 7 — demo, ablations, report (Days 12-14)

**Freeze code at the end of Day 12. Days 13-14 are writing and demo polish only.**

- WhatsApp-style UI, verdict card, evidence trail with highlighted spans, visible confidence
- Error analysis: ten real failure cases per language, discussed
- Full ablation tables
- Ethics section: scope limits, no political-opinion adjudication, sources always shown

## Claude Code setup

Anthropic's own guidance is that the harness — CLAUDE.md files, hooks, skills, plugins, MCP servers — determines how Claude Code performs more than the model does, and that the order you build them in matters. Build in order. CLAUDE.md first. Don't touch MCP until the basics work.

### Repo layout

```
truthlens/
├── CLAUDE.md                  # root — pointers + gotchas only
├── .claude/
│   ├── settings.json          # permissions, pre-allowed commands
│   ├── commands/              # /run-eval, /new-experiment, /ablation
│   └── agents/                # data-inspector (read-only)
├── data/
│   ├── raw/                   # gitignored
│   ├── splits/                # COMMITTED. never regenerated.
│   └── CLAUDE.md              # dataset provenance, schema, gotchas
├── src/
│   ├── preprocess/            # LID, script, transliteration
│   ├── claims/                # checkworthiness, span ID, normalization
│   ├── matching/              # MultiClaim retrieval
│   ├── retrieval/             # BM25 + dense   + CLAUDE.md
│   ├── stance/                # BiLSTM + XLM-R
│   ├── generation/            # mT5 / IndicBART
│   ├── faithfulness/          # NLI, calibration, abstention
│   └── eval/                  # evaluate.py — the only place metrics exist
├── configs/                   # one YAML per experiment
├── results/                   # one JSON per run, committed
├── tests/
├── notebooks/                 # plots only, never logic
└── app/                       # FastAPI + UI
```

Claude loads CLAUDE.md files additively as it walks the tree, so the root file should be pointers and critical gotchas only. Per-module detail goes in subdirectory files.

### Root CLAUDE.md

```markdown
# TruthLens

Multilingual claim verification for WhatsApp forwards (EN / HI / PA),
including Romanized Hindi and Punjabi. Solo student project, CSE472.

## Non-negotiable rules
- NEVER regenerate files in data/splits/. They are frozen and committed.
  If a split file seems wrong, stop and ask.
- Every experiment writes results/{config_hash}.json. No exceptions.
- Every run sets seed=42 in numpy, torch, random, and transformers.
- No metric is ever computed inline in a notebook. Only via src/eval/evaluate.py.
- Compare every model against the dumb baseline in the same table.
  A model without a baseline comparison is not a result.

## Metric definitions (do not improvise alternatives)
- Retrieval: Recall@{1,5,10}, MRR, Success@10
- Verdict: macro-F1 over {Supported, Refuted, NEI, NotAClaim}
- Faithfulness: NLI entailment of the explanation w.r.t. retrieved evidence
- All metrics reported per-language AND per-script (native vs romanized)

## Commands
- Eval:    `make eval CONFIG=configs/<name>.yaml`
- Test:    `pytest tests/ -q`
- Lint:    `ruff check src/`
- Leakage: `pytest tests/test_no_leakage.py`  (run after ANY data change)

## Stack
Python 3.11, PyTorch, HuggingFace transformers, sentence-transformers,
FAISS, rank_bm25, IndicXlit (AI4Bharat), fastText LID, FastAPI.

## Gotchas
- LaBSE is for bitext alignment and the t-SNE plot ONLY. Retrieval uses BGE-M3.
- Punjabi has ~346 X-CLAIM training examples. Any Punjabi result above
  English-level performance is a bug, not a breakthrough.
- Romanized input is the primary use case, not an edge case.
- Target accuracy is ~50% on AVeriTeC-style data. That is competitive with
  published SOTA. Do not tune toward suspiciously high numbers.

## Where things live
- data/CLAUDE.md           — dataset provenance and schemas
- src/retrieval/CLAUDE.md  — retrieval conventions
- docs/phase-plan.md       — current phase and what is in scope
```

### Session discipline

This is where most of the benefit is won or lost.

- **Always start in plan mode** (Shift+Tab) for anything touching more than one file. Claude can read and reason but cannot write to disk; it presents a plan, you approve, then it executes. Approve, switch to accept-edits, let it run.
- **One phase per session.** `/clear` between phases, `/compact` within one when context fills. `/context` shows what is eating the window.
- **Commit before every task.** Always one `git reset` from the last good state. `/rewind` or double-Esc also undoes edits without touching git.
- **Let it loop against the eval harness.** This is the single biggest quality multiplier for ML work and the whole reason Phase 0 exists. Not "write a retriever" but: *"implement BM25 in src/retrieval/, run `make eval CONFIG=configs/bm25_baseline.yaml`, iterate until Recall@10 exceeds 0.45 on dev, show me the results JSON after each attempt."*
- **Use a read-only subagent for exploration.** Dataset profiling is context-hungry. A `data-inspector` agent that reads, profiles and writes a markdown summary keeps that out of the main session.
- **Challenge the work.** Two prompts worth overusing: *"grill me on these changes — prove to me this works"* and, after a mediocre fix, *"knowing everything you know now, scrap this and implement the elegant solution."*

### Starter prompts

**Session 1 — scaffolding**

> Read the attached project doc. Plan mode only, don't write anything yet. Propose a repo structure and a Phase 0 scaffolding plan: directory layout, pinned dependencies, a frozen-splits convention, an eval harness that takes a predictions JSONL and a config YAML and emits metrics JSON, and a leakage test. No model code. Show me the plan and wait for approval.

**Session 2 — data**

> Phase 0, step 2. Write `src/data/` loaders for AVeriTeC, X-CLAIM, and CheckThat!-2025-Task-2. For each: download instructions in data/CLAUDE.md, a loader returning a common schema, and a profiling script reporting per-language and per-split counts. Then build frozen splits into data/splits/ and make `pytest tests/test_no_leakage.py` pass. Do not touch models.

**Session 3 — vertical slice**

> Phase 1. Build the thinnest possible end-to-end English pipeline: AVeriTeC dev claims → BM25 over the AVeriTeC knowledge store → an off-the-shelf NLI model for a 4-class verdict → a template explanation with source links → a FastAPI POST /verify endpoint. Quality doesn't matter; working end-to-end does. Run `make eval` and give me the baseline numbers.

**Every experiment session thereafter**

> Plan mode. I want to add \[X\]. Before proposing code: (1) what's the current number for this component in results/, (2) what's the dumb baseline, (3) what would make this experiment invalid. Then propose the change as a new config file plus a minimal code diff.

## Results log

Fill this in as each number lands. A row without a baseline is not a result — it is a number.

| Component | Metric | Dumb baseline | Current | Published reference |
| --- | --- | --- | --- | --- |
| Claim matching (EN) | Success@10 | random rank | — | SemEval-2025 T7 leaderboard |
| Claim matching (HI) | Success@10 | random rank | — | — |
| Claim matching (PA) | Success@10 | random rank | — | — |
| Claim matching (romanized HI) | Success@10 | — | — | — |
| Evidence retrieval (EN) | Recall@10, MRR | BM25 | — | — |
| Evidence retrieval (HI) | Recall@10, MRR | BM25 | — | — |
| Claim span ID (EN) | token F1 | whole-post span | — | X-CLAIM mDeBERTa baseline |
| Claim span ID (HI) | token F1 | whole-post span | — | X-CLAIM mDeBERTa baseline |
| Claim span ID (PA) | token F1 | whole-post span | — | X-CLAIM mDeBERTa baseline |
| Check-worthiness | macro-F1 | majority class | — | — |
| Stance (BiLSTM) | macro-F1 | TF-IDF + LR | — | — |
| Stance (XLM-R) | macro-F1 | BiLSTM | — | — |
| Verdict, 5-class | macro-F1 | majority class | — | AVeriTeC \~47-50% acc |
| Explanation faithfulness | NLI entailment rate | — | — | — |
| Abstention | acc @ 60% coverage | acc @ 100% | — | — |

### The comparison that matters most

Every row above should eventually exist twice: once on native script, once on romanized. The **gap between the two columns** is the finding. Where the gap is largest is where the pipeline is most fragile, and that is the sentence the report is built around.

## Open questions and risks

### To resolve this week

- [ ] **Submission deadline.** The 13-week plan is an assumption. A shorter runway means merging Phases 5 and 6 and cutting items 1 and 2 from the cut list immediately.
- [x] **Compute. Settled:** local RTX 4050 laptop GPU, 6 GB VRAM, no Colab. So: XLM-R-**base** not large, IndicBART not mT5, LoRA throughout, fp16, one training job at a time and never alongside the API server. Inference budget and per-model VRAM in `specs/SYSTEM_DESIGN.md` §10.
- [ ] **MultiClaim access.** The Zenodo record is marked restricted — request access early, it may take days. The SemEval-2025 T7 release is the fallback.
- [ ] **AVeriTeC knowledge store size.** Roughly 1000 articles per claim across 4568 claims is large. Check disk before downloading; a subset may be necessary.

### Standing risks

| Risk | Mitigation |
| --- | --- |
| Verdict accuracy plateaus low | Expected and defensible. Lean on the abstention and calibration story: a system that knows when it doesn't know. Cite the \~47-50% published figure. |
| Punjabi data is thin (346 train) | Report per-language results honestly and frame as low-resource evaluation. A Punjabi score above English is a leak, not a win. |
| Silent data leakage | `tests/test_no_leakage.py` in CI, frozen committed splits, dumb baseline in every table. |
| Transliteration errors cascade | IndicXlit is word-level. Measure transliteration accuracy on Dakshina *separately* so pipeline failures can be attributed correctly. |
| Scope creep via Claude Code | It will happily build anything asked. Plan mode, one phase per session, and the cut list are the defence. |
| Ethics / censorship framing in viva | Verdicts always show sources, the system explains rather than labels, explicit scope limits, no political-opinion adjudication. Write this section early, not at the end. |

### Things deliberately not being done

Worth stating in the report so they read as decisions rather than omissions.

- No image or video claims — text only
- No political-opinion or subjective-claim adjudication
- No claim of deployment readiness; this is a research prototype
- No redistribution of any scraped or licensed dataset
