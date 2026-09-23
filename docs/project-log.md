# TruthLens — project log

**Read this first in any new session.** It is the running record of what has
been built, what was decided and why, and what is next. When the context
window is compacted, this file is what carries the project forward.

Append to it; do not rewrite history. Every entry is dated. If a decision is
reversed, add a new entry saying so rather than editing the old one — the
reasoning that turned out wrong is still evidence.

**Related files:** `CLAUDE.md` (rules and conventions) · `docs/specs/` (PRD,
SRS, SYSTEM_DESIGN, UI_UX — what is being built) · `docs/phase-plan.md` (where
we are in the phase order) · `docs/build-plan.md` (historical rationale) ·
`docs/data-profile.md` (generated counts) · `docs/results.md` (generated
results tables) · `docs/environment.md` (toolchain).

**Precedence when they disagree:** code and tests > `CLAUDE.md` > `docs/specs/`
> `docs/build-plan.md`.

---

## Resuming cold — read this first

If you have just been handed this project with no memory of it, this section is
enough to start work without re-deriving anything.

**What it is.** TruthLens checks forwarded WhatsApp messages in English, Hindi
and Punjabi, including Hindi/Punjabi typed in Latin letters. Solo student
project, CSE472, 14 days.

**Where to look, in order.** `CLAUDE.md` (rules, precedence, gotchas) →
`docs/phase-plan.md` (where we are, what is next) → `docs/specs/` (what is being
built) → this log (why things are the way they are). `docs/build-plan.md` is
historical rationale, lowest precedence.

**Precedence when documents disagree:** code and tests > `CLAUDE.md` >
`docs/specs/` > `docs/build-plan.md`.

**Five things that are easy to get wrong here:**

1. **Accuracy is close to meaningless on AVeriTeC.** Majority class scores 61%.
   Lead with macro-F1, always beside its baseline.
2. **The language column is not the script column.** Script is detected per row
   by `src/data/script_id.py`, never inferred from a filename or lang field.
3. **Never regenerate a committed split.** Frozen means committed. If one looks
   wrong, stop and ask — `make leakage` after any data change.
4. **CI has no torch.** Nothing under `src/` may import a model library at
   module scope; stages import lazily inside methods.
5. **The harness refuses rather than guessing.** If `make eval` exits 2, read
   the message — do not work around it.

**To get running:** `make setup` then `make test`. The environment is already
built on this machine (Python 3.11 via uv, CUDA torch, models cached on `D:`).

---

## Status at a glance

| | |
| --- | --- |
| **Current phase** | **Phase 1 complete, gaps closed, MultiClaim ingested.** Phase 2 not started, nothing blocking it. |
| **Clock** | 14 days. **Day 1 done** (Phase 1). Day 2 = Phase 2, not started. Freeze end of Day 12. |
| **Hardware** | i7-14700HX + RTX 4050 laptop GPU, 6 GB VRAM. No Colab. |
| **Branch model** | Trunk-based. Everything commits straight to `main`. |
| **Python** | 3.11.16 via uv, in `.venv`. System Python is 3.13 and is not used. |
| **Tests** | 204 passing, 1 skipped, 1 gpu-deselected |
| **Datasets in hand** | AVeriTeC, X-CLAIM, **MultiClaim** |
| **Datasets waiting** | CheckThat! 2025 T2 (not started), Dakshina (not downloaded) |
| **GPU stack** | torch `2.9.1+cu128`, CUDA available on the RTX 4050. ~4.9 GiB usable VRAM. |
| **Models trained** | None. Phase 1 uses off-the-shelf NLI only; training starts Phase 3. |
| **Numbers so far** | Retrieval Recall@10 0.0947 (floor 0.0121) · verdict macro-F1 0.2147 (majority 0.1516) |
| **CI** | Green. Last verified run 29s, both jobs. |

---

## 2026-09-20 — Phase 0: the harness, before any model

**Why first.** The dominant failure mode in agent-assisted ML is not broken
code, it is plausible code that runs, produces a number, and is silently
wrong. Phase 0 builds the thing that catches that.

### Built

| Piece | Where |
| --- | --- |
| Eval harness | `src/eval/evaluate.py` — predictions JSONL + config YAML → `results/{config_hash}.json` |
| Metrics | `src/eval/metrics.py` — pure functions, cross-checked against scikit-learn |
| Dumb baselines | `src/eval/baselines.py` — generate predictions, so they travel the same path a model does |
| Leakage detection | `src/data/leakage.py` — 4 checks |
| Frozen splits | `data/splits/` + `SPLITS.lock`, enforced in four places |
| Results tables | `src/eval/report.py` → `docs/results.md` |
| CI | `.github/workflows/ci.yml` — lint, tests, leakage, end-to-end eval |

### Five guardrails, each enforcing a rule already in CLAUDE.md

1. `baseline:` is mandatory — no baseline, no results file
2. a `test` split aborts unless `TRUTHLENS_ALLOW_TEST=1`
3. a split disagreeing with `SPLITS.lock` aborts
4. a metric above `sanity_ceiling` writes a loud warning
5. duplicate / unknown / missing uids abort unless `allow_partial`

### Decisions and why

- **Splits are ID manifests, not text.** Keeps the repo publishable without
  redistributing licensed data. Near-duplicate detection still works in CI via
  a 64-bit SimHash stored in the manifest (16 hex chars per row).
- **SimHash thresholds were calibrated, not assumed.** Measured on this
  project's own text: trivial variants 0–4 Hamming, word substitutions ~10,
  unrelated claims 22+. Fail at 8, warn at 14.
- **Stated limitation:** this catches duplicates and trivial variants, *not*
  semantic paraphrase. Embedding-based detection belongs in Phase 4.
- **Trunk-based git.** Phase branches were ceremony on a solo repo; a two-week
  branch is deferred integration, not isolation.

### Bugs the tests caught in the harness itself

Lock keys written as absolute paths (unusable in CI); the split parsed before
its integrity was checked (tampering surfaced as a confusing JSON error); a
bad label crashed instead of refusing; `.gitattributes` had the catch-all `*`
last, where it silently overrode every `-text` protection on the frozen splits.

---

## 2026-09-20 — Verdict scheme widened to 5 classes

`Supported / Refuted / Conflicting / NEI / NotAClaim`.

AVeriTeC ships `Conflicting Evidence/Cherrypicking`, which the old 4-class
scheme had nowhere to put. The alternative was collapsing it into NEI, which
throws away a distinction AVeriTeC paid annotators to make and makes NEI mean
two different things at once.

Mapping is in `src/data/labels.py`. `verdict_4class` was **removed**, not kept
as an alias — two competing schemes is exactly how a label set rots.

**Two consequences to state in the report, not discover in the viva:**

- `NotAClaim` has zero support on AVeriTeC-only runs (AVeriTeC claims are all
  already claims), so macro-F1 there is **structurally capped at 0.80**.
- `Conflicting` is rare (~7%). Read its per-class F1 next to its support.

---

## 2026-09-20 — Data acquisition: AVeriTeC and X-CLAIM

`make data` — fetch, build splits, profile, check. Sources and the sha256 of
every file are in `data/raw/DOWNLOADS.json`.

### What landed

| Dataset | train | dev | test |
| --- | --- | --- | --- |
| averitec | 2666 | 500 | 307 |
| x_claim | 5343 | 600 | 571 |

X-CLAIM raw counts matched the paper exactly (EN 3891/400/371, HI 1193/100/100,
PA 346/100/100) before dedup — a good sign the loader is reading it right.

### Decisions and why

- **AVeriTeC's test split is withheld** for the FEVER shared task. Held out
  10% of the public train, stratified by label, seed 42, as a local test set.
  The official dev split is used unchanged so dev numbers stay comparable to
  published work. Our train is correspondingly smaller than the official one.
- **`en2xx` X-CLAIM files deliberately not downloaded.** They are machine
  translated; X-CLAIM's own finding is that joint multilingual training beats
  English-translated training, and mixing them in would undermine that
  ablation.
- **Freeze now means committed, not merely written.** A split file git has
  never seen is still being built and can be overwritten freely. Requiring the
  full override ceremony for those would only teach the habit of reaching for
  the override.

### The leakage test failed on real data — as designed

First run: **49 failures in AVeriTeC, 55 in X-CLAIM.** Root cause, diagnosed
against the raw files:

| Source of overlap | Count |
| --- | --- |
| AVeriTeC official `train.json` internal duplicates | 71 (2997 unique of 3068) |
| AVeriTeC official `train` ∩ `dev` | 4 — **upstream** |
| X-CLAIM `en` train∩dev / train∩test | 3 / 2 — **upstream** |
| X-CLAIM cross-language (same post in `pa` and `hi` files) | 2 |

This is the DS@GT CheckThat! 2025 finding reproduced, and it is a reportable
result rather than a bug.

**Policy adopted: train yields to eval.** Drop the offending row from *train*,
never from dev/test — shrinking an eval split silently changes the benchmark
and makes our numbers incomparable with published ones. Dropped 94 train rows
from AVeriTeC, 87 from X-CLAIM. Dev and test were not modified at all.

**Two X-CLAIM dev↔test pairs are irreducible** (Jaccard 0.906, 0.990); both
sides are official eval splits. Accepted by exact uid pair in
`data/splits/KNOWN_LEAKAGE.json` with a written reason. Anything not on that
list still fails. Bounds dev→test contamination at 2/571 = **0.35%**.

### Two findings worth carrying into every later phase

1. **The AVeriTeC majority-class baseline is 58–61% accuracy** — *higher* than
   the ~50% figure the build plan cites as competitive SOTA. Accuracy is
   therefore close to useless on this data; always-predict-Refuted beats
   published systems on it. **Macro-F1 is the metric that means something**,
   and every accuracy number must be shown next to the majority baseline.
2. **Punjabi is 26.5% non-native script in X-CLAIM train.** The language
   column is not the script column: `train-pa.csv` holds 249 Gurmukhi, 54
   Devanagari and 36 Latin rows. Script is detected per row
   (`src/data/script_id.py`) and never inferred from the filename.

---

## 2026-09-21 — Specs added; 14-day timeline; hardware settled

Four specification documents landed in `docs/specs/`. This entry records what
they own, what changed around them, and every place they disagreed with the code.

### What each document owns

| Document | Owns | Does not own |
| --- | --- | --- |
| `PRD.md` | Why and for whom: problem, users, scenarios, scope priorities, success bars | Testable requirements |
| `SRS.md` | Numbered requirements (FR-1…FR-27, NFR-1…NFR-12), each with a verification method | Why they exist; how they are built |
| `SYSTEM_DESIGN.md` | Stage contracts, data models, API schema, GPU budget, failure handling | Requirements; screens |
| `UI_UX.md` | Screens, states, verdict card, copy, accessibility, demo script | Response fields |

**Precedence, now written into `CLAUDE.md`:** code and tests > `CLAUDE.md` >
`docs/specs/` > `docs/build-plan.md`. The build plan is reclassified as
historical rationale and carries a header note saying so. Its embedded copy of
an older `CLAUDE.md` and its session starter prompts still describe the 4-class
scheme; they are left as written rather than back-dated.

### Timeline and hardware

13 weeks became **14 days**, Day 1 = the first day of Phase 1. Phase 1 Day 1 ·
Phase 2 Days 2-3 · Phase 3 Day 4 · Phase 4 Days 5-6 · Phase 5 Days 7-8 ·
Phase 6 Days 9-11 · Phase 7 Days 12-14, **code freeze end of Day 12**.

Added rule: **if MultiClaim is not approved by Day 5, swap Phases 4 and 5** and
do evidence retrieval first. The fast path is reordered, never cut.

Hardware settled: **i7-14700HX + RTX 4050 laptop GPU, 6 GB VRAM, no Colab.**
That closes the build plan's open "Compute" question and fixes the model sizes:
XLM-R-base not large, LoRA throughout, fp16, one training job at a time.

### Phase 6 generator: IndicBART, decided

Was "mT5 or IndicBART". Now IndicBART, for two reasons in order: it fits
(244M, ~0.5 GB fp16, inside a 5.5 GB inference ceiling alongside ~2.3 GB of
other resident weights), and it is an encoder-decoder, so the Unit IV
seq2seq-with-attention requirement is satisfied by attention over the actual
evidence passages rather than by a figure that means nothing.

**Considered and rejected: a modern small instruction-tuned model** (Qwen2.5-3B
via QLoRA). It would likely produce more fluent Hindi explanations and would
physically fit at 4-bit. Rejected **to protect the timeline, not on quality** —
a new quantisation and adapter stack on day 9 of 14 can eat two days and return
a model that generates beautifully and cites nothing.

If Days 9-11 have slack, spend it on a **prompted-LLM comparison** rather than
on mT5-small. It answers the obvious viva question ("why not just prompt an
LLM?") with a number instead of an opinion.

### Conflicts found, and how each was resolved

Spec vs code — the code won every time, per the precedence rule:

| Conflict | Resolution |
| --- | --- |
| `Script` Literal included `"mixed"`, and FR-4 claimed `script_id.py` detects it. It does not — `detect_script()` returns `deva`/`guru`/`latn` only | Dropped `"mixed"`. Added `script_purity: float` to `Preprocessed`, reusing the existing `script_id.script_purity()`. A fourth enum value would have created a new per-script cell and changed the native-vs-romanized table |
| `Lang` includes `"other"`; `splits.py LANGS` does not | Not a real conflict — `other` is runtime-only, never a split row. Stated explicitly so nobody "fixes" the split schema to match |
| `SYSTEM_DESIGN` §13 presented `make index` and `make serve` as existing | Marked both new-in-Phase-1. `make setup-ml` does exist |

Spec vs spec:

| Conflict | Resolution |
| --- | --- |
| `UI_UX` §7 requires the confidence-band cut points from `/version` and forbids hard-coding them; `SYSTEM_DESIGN` §8 and FR-21 both omitted them, leaving the UI no legal source | Added `confidence_bands: {high, medium}` to the `/version` payload and to FR-21 |
| The abstain → template-explanation rule was in `SYSTEM_DESIGN` §2 prose and the diagram, but missing from §11's failure table where every other degradation rule lives | Added the row to §11 |

Docs vs reality:

| Conflict | Resolution |
| --- | --- |
| `environment.md` said to install the **CPU** torch build | Corrected to the CUDA build, with a verification snippet and an instruction to record the resolved build string. A CPU wheel installs silently and trains ~20x slower — on 14 days that is most of the project |
| `phase-plan.md` said loaders were not started, splits had no data, and the AVeriTeC label mapping was undecided | All four were done. Rewritten |
| `build-plan.md` Phase 1 and its results-log row still said 4-class | Both now 5-class |

### Carried forward as open questions

- **`mixed` as a fourth script value** — decided against for now (it would change
  the harness breakdown vocabulary), but it is a product question as much as a
  technical one and can be revisited in Phase 2.
- **No transliteration package is pinned.** `CLAUDE.md` promises IndicXlit;
  `requirements-ml.txt` contains nothing that can transliterate. FR-5 is P0 and
  all of Phase 2 depends on it. The Day-2 install spike is scheduled, but the
  lock needs an entry either way.
- **`requirements-ml.in` still has Colab comments** (`peft ... free-tier Colab
  contingency`). Cosmetic, left alone in a docs-only change.


## 2026-09-21 — Phase 1 unblocked: GPU stack, knowledge store, transliteration

Everything listed as blocking Phase 1 is cleared. Nothing here is model code;
this is the environment and the data Phase 1 will consume.

### AVeriTeC knowledge store

`make kb` → `scripts/download_knowledge_store.py`. Downloaded the **dev** store,
**11.54 GB**, sha256 recorded in `data/raw/averitec_kb/DOWNLOADS.json`.

Sizes, measured from the HF API rather than estimated:

| Split | Size |
| --- | --- |
| dev | 11.54 GB ← downloaded, all Phase 1 needs |
| train | 63.52 GB |
| test | 40.71 GB |
| **all** | **115.78 GB — would not have fit in 112 GB free** |

The old note said "check size before downloading; a subset is likely
necessary". It was: the full store does not fit on this disk, and dev being a
separate file is what makes Phase 1 possible at all.

**Do not extract it.** 11.54 GB compressed → **36.55 GB** uncompressed (x3.2).
It holds 500 members, `output_dev/{0..499}.json`, one per dev claim, so a
claim's candidates are read straight from the archive. Extracting buys nothing.

Verified end to end before trusting it: all 500 ids present, `claim_id` inside
each file agrees with its filename, and our split's `source_id`
(`averitec:dev.json:133`) parses directly to `output_dev/133.json`. Each claim
carries ~800–1500 candidate documents, of which **`type == "gold"` (2–4 per
claim) is the annotated evidence** — Phase 1's retrieval gold, free.

Retrieval ranks **within one claim's pool**, which is AVeriTeC's own protocol
and what keeps our Recall@k comparable with published numbers.

### The download had to be written, not run

`huggingface.co` fails on this connection: **0 of 12 attempts** succeeded, TLS
reset mid-handshake. The short alias **`hf.co` works**, and serves HTTP 206, so
the fetcher uses it with Range resumption and backoff. It survived several
reconnects across 11.5 GB. This applies to model downloads too — use `hf.co`.

### GPU stack

`torch==2.9.1+cu128`, verified: `cuda.is_available() == True`, device "NVIDIA
GeForce RTX 4050 Laptop GPU", 6.00 GiB, `sm_89`, a real matmul on device.
Driver 610.62 / CUDA UMD 13.3, so cu121–cu128 were all viable; cu128 is the
newest with Windows py311 wheels.

**A trap found and closed.** `requirements-ml.txt` pinned `torch==2.14.0`,
pulled in by `sentence-transformers` and `transformers`. On Windows the PyPI
wheel is CPU-only, so `uv pip install -r requirements-ml.txt` would have
silently replaced the CUDA build with a CPU one — the exact failure
`environment.md` warns about, sitting inside the lock meant to prevent it, and
the document claimed "torch is deliberately not in any lock" while it was.
Now compiled with `--no-emit-package torch`, and `make setup-ml` asserts
`'+cu' in torch.__version__` after installing so a regression fails loudly.

### Measured: real VRAM is ~4.9 GiB, not 5.5 GB

On an idle desktop only **4.96 of the 6.00 GiB is free** — Windows WDDM holds
about 1 GiB for compositing, and a browser takes more. NFR-3's 5.5 GB ceiling
is not reachable in practice. SYSTEM_DESIGN §10's ~2.8 GB of resident weights
still fits, but the headroom for activations is ~2 GiB, not 2.7 GB. Recorded in
`environment.md` with the consequences: close the browser before training, one
model at a time, and if something does not fit try batch size and gradient
checkpointing before reaching for a smaller model.

### Transliteration is no longer an open gap

`ai4bharat-transliteration` (IndicXlit) **depends on fairseq** — confirmed from
its PyPI metadata, not assumed — which does not install cleanly on Windows +
Python 3.11. So `indic-transliteration` 2.3.82 (pure Python, no heavy deps) and
`indic-nlp-library` are pinned as the **baseline**, not as a contingency.
Verified working: `namaste bharat` → `नमस्ते भरत्`.

The Day-2 spike now tries IndicXlit as an **upgrade** measured against a
working baseline on Dakshina, rather than as a dependency Phase 2 is blocked
on. Also cleaned the stale "free-tier Colab contingency" comment off `peft`.

### Still open

- **MultiClaim** — awaiting Zenodo approval. Swap Phases 4 and 5 if not
  granted by Day 5.
- **CheckThat! 2025 Task 2** — not started, needed for Phase 3.
- **Knowledge store train split** (63.52 GB) — not downloaded. Only needed if
  training retrieval on AVeriTeC train; dev covers Phase 1 and evaluation.


## 2026-09-21 — Caches moved off C:, and a correction

### C: was full, which would have broken Day 1

`C:` had **1.5 GB free of 245 GB** while `HF_HOME`, the uv cache and the pip
cache all defaulted there. The first model download — BGE-M3, 2.27 GB — would
have failed, and the error would have looked like a network problem rather
than a disk one.

Cleared 12.6 GB of rebuildable cache (`uv cache clean` 4.9 GB, `pip cache
purge` 7.8 GB) and redirected all three to D: as persistent user environment
variables: `HF_HOME=D:\hf-cache`, `UV_CACHE_DIR=D:\uv-cache`,
`PIP_CACHE_DIR=D:\pip-cache`. C: went from 1.5 GB free to 21 GB.

They live outside the project directory deliberately, so `git clean -xdf` can
never delete 17 GB of model weights. Verified with a real download:
`hf_hub_download('ai4bharat/IndicBART', 'config.json')` landed under
`D:\hf-cache\hub\`. Symlinks are permitted here, so the cache stores each blob
once rather than doubling.

### Correction: the hf.co advice was wrong

The previous entry, `data/CLAUDE.md` and the downloader's comment all said
`huggingface.co` fails on this connection (measured 0/12) and that `hf.co`
should be used instead. **That was a transient observation reported as a
property of the hostname.** Re-measured in the same session:

| Endpoint | Sample 1 | Sample 2 |
| --- | --- | --- |
| `huggingface.co` | 0/12 | 5/10 |
| `hf.co` | worked | 4/10 |

Neither is reliably better. The connection to the Hub is simply intermittent,
around half of requests failing either way. The right conclusion is the one
the downloader already implements — **resume, don't retry from zero** — not a
hostname swap. All three places are corrected. The resumable fetcher stands;
only the reason for it changed.

Worth doing before pulling the ~17 GB of models: set `HF_TOKEN`. It raises the
rate limit, though it will not stop the dropped connections.

### Space, measured

Asked what the whole project needs. Real numbers rather than estimates:

| Item | Size |
| --- | --- |
| On disk now (venv 5 GB + KB zip 11 GB + data) | 16 GB |
| Models, 7 of them, from the HF API | ~17 GB |
| Dakshina (confirmed 2.01 GB tar, + extracted) | ~4 GB |
| MultiClaim | ~1–3 GB **estimated** — Zenodo record restricted, file list withheld |
| CheckThat! T2, SemEval-2023 T3 | <1 GB |
| Indexes, checkpoints, working headroom | ~11 GB |
| **Realistic total** | **~50 GB**, against 112 GB free |

Two findings that change plans rather than just the budget:

- **Extracting the dev knowledge store is not worth it.** Reading a member
  straight from the zip runs at **224 MB/s** (median 65.6 MB claim file in
  0.29 s), so a full pass over all 500 claims is ~3 minutes. Extraction costs
  36.55 GB to save a couple of minutes on a pass that happens once. There is
  also no dedup win — URLs are 100% unique within a claim.
- **A dense index over the full dev knowledge store is not feasible on this
  GPU.** 30.6 G characters ≈ 15.3 M passages at ~512 tokens → **31.3 GB of
  fp16 vectors and 14–28 GPU-hours** on the 4050. `SYSTEM_DESIGN.md` §7 budgets
  ≤3 GB for it. The fix is standard retrieve-then-rerank: BM25 to top-100 per
  claim, dense re-rank only those → ~150k passages, ~0.3 GB, ~15 minutes.
  **Decide this before Phase 5, not during it.**


## 2026-09-21 — Day 1, Phase 1: the vertical slice runs

English claim in → BM25 over its AVeriTeC candidate pool → mDeBERTa NLI stance
→ the §6 rule aggregator → template explanation → `POST /verify` → a plain HTML
page. Ugly, working, committed. **These numbers are the floor everything later
has to beat.**

### The numbers

Retrieval, BM25 against a seeded random ranking of the *same* per-claim pools:

| Metric | BM25 | Random floor | Ratio |
| --- | --- | --- | --- |
| Recall@1 | 0.0200 | 0.0023 | 8.7x |
| Recall@5 | 0.0613 | 0.0068 | 9.0x |
| Recall@10 | **0.0947** | 0.0121 | 7.8x |
| MRR | 0.0656 | 0.0081 | 8.1x |
| Success@10 | **0.1580** | 0.0240 | 6.6x |

Verdict, 5-class on AVeriTeC dev (500 claims):

| Metric | Pipeline | majority_class |
| --- | --- | --- |
| macro-F1 | **0.2147** | 0.1516 |
| accuracy | 0.3600 | **0.6100** |

**The accuracy row is the one to read carefully.** The pipeline loses to
always-predicting-Refuted by 25 points of accuracy while beating it by 6 points
of macro-F1. That is exactly the trap `CLAUDE.md` warns about: 61% of dev is
Refuted, so accuracy rewards a model for refusing to ever say anything else.
Macro-F1 is the number that means something, and it is what gets reported.

Per class, which is where the diagnosis is:

| Class | P | R | F1 | support |
| --- | --- | --- | --- | --- |
| Refuted | 0.708 | 0.446 | 0.547 | 305 |
| Supported | 0.324 | 0.189 | 0.238 | 122 |
| NEI | 0.135 | 0.371 | 0.198 | 35 |
| Conflicting | 0.057 | 0.211 | 0.089 | 38 |
| NotAClaim | — | — | 0.000 | 0 |

### Two things the numbers say, both actionable

**1. Retrieval is the bottleneck, not stance.** Success@10 of 0.158 means
roughly five claims in six have *no* gold document anywhere in the top 10, so
the stance model is mostly reading irrelevant text and the verdict is bounded
by that. Improving the aggregator before improving retrieval would be tuning
against noise. Phase 5's dense retrieval is where the verdict number moves.

**2. The rule aggregator over-fires `Conflicting` by 3.7x** — 141 predicted
against 38 actual, precision 0.057. The §6 rule takes max P(Supports) and max
P(Refutes) *across all k passages*, so with k=10 mostly-irrelevant passages, one
stray confident-support and one stray confident-refute is enough. The rule is
not wrong; it is being fed a pool it was not designed for. Worth an ablation on
k, and a concrete argument for the learned aggregator in Phase 6.

### Is BM25 at Recall@10 = 0.095 believable?

Low, and plausibly so: ~1013 candidate documents per claim with 2.19 gold among
them (0.2%), documents are whole scraped web pages, and claims are one short
sentence. The random floor lands at 0.012, close to the ~1% arithmetic predicts,
which says the pool is not filtered and the evaluation is measuring something
real. A high number here would have meant gold leaked into the ranking.

One known handicap, deliberately visible: **documents are truncated to 4000
characters** by the KB cache. That is a config parameter, not a hidden
simplification — rebuild the cache at a different limit and rerun to price it.
Worth doing in Phase 5 alongside dense retrieval.

### Built

| Piece | Where |
| --- | --- |
| Contracts | `src/pipeline/contracts.py` — §4 models, labels imported from `data/labels.py` |
| Registry | `src/pipeline/registry.py` — `(stage, impl)` to class, chosen by config |
| Orchestrator | `src/pipeline/orchestrator.py` — the §6 flow, degradation recorded in the trace |
| Batch runner | `src/pipeline/batch.py` — same orchestrator, over a frozen split |
| Baselines | passthrough preprocess/claims, `none` matcher, BM25 + random retrieval, NLI + always-neutral stance, rule aggregator, template explainer, stub faithfulness |
| API | `app/main.py` — `/verify`, `/health`, `/version` |
| UI | `app/static/index.html` — plain, unstyled; Phase 7 styles it |
| KB tooling | `scripts/build_kb_cache.py`, `scripts/build_retrieval_gold.py` |

69 new tests (152 total). Live API verified: `/health` reports `degraded` until
the NLI model loads, `/version` serves the tau values and confidence bands, and
`POST /verify` on dev claim 133 returns Refuted at 0.786 with 10 passages and a
full stage trace. **Warm latency 0.67 s mean, 0.75 s max** against NFR-1's 10 s
target; the 14.6 s first request is model load, which is NFR-2's cold start.

### Decisions worth keeping

- **A one-time KB cache.** `scripts/build_kb_cache.py` flattens the 11.5 GB zip
  into per-claim JSONL in 11.3 minutes. Retrieval runs then take seconds rather
  than re-parsing the archive every time. 500 claims, 506,349 documents, 1,096
  gold, 1.2 GB.
- **The retrieval floor is a chained run, not a harness change.** The registered
  `random_rank` samples one global pool; ours are per claim. Running the random
  ranking through the same batch runner and naming its `config_hash` as the
  BM25 run's baseline uses a feature `evaluate.py` already had.
- **Retrieval ranks documents by URL**, because that is the unit AVeriTeC
  annotates gold at. No harness change needed.

### A bug the tests caught before it could mislead

Paragraph selection originally used BM25 to pick which paragraph of a document
the NLI model reads. `rank_bm25` with few documents returns **idf = 0 for every
term** — with two paragraphs, log(1.5) minus log(1.5) — so every score came out
0.0 and `max()` silently returned the *first* paragraph regardless of content.
The pipeline would have kept producing verdicts, formed from the wrong text.
Replaced with length-damped lexical overlap in `src/retrieval/passages.py`,
which degrades sensibly at any size, and both retrievers now share it so the
only difference between BM25 and the floor is the ranking itself.


## 2026-09-22 — Phase 1 gaps closed; MultiClaim ingested

### Phase 1 gaps

Five gaps found by auditing Phase 1 against the specs rather than against my
own summary of it. All closed. 194 tests, up from 152.

| Gap | Closed by |
| --- | --- |
| `app/static/` was one file; §5 specifies `index.html`, `app.js`, `styles.css`, `i18n/` | Split out, with `i18n/{en,hi,pa}.json` carrying the verdict labels from `UI_UX.md` §6 |
| No stage tests for preprocess, claims, generation, faithfulness | `tests/test_stage_*.py` for each |
| **FR-2 implemented but untested** | `tests/test_stage_preprocess.py` |
| §12 wants a golden trace per path; `fast` was missing | Stub matcher in `tests/test_orchestrator.py` — all five paths now covered |
| `make index` in §13 does not exist | Spec corrected: Phase 1 needs no persistent index |

Two specification statements were corrected rather than the code, per the
precedence rule:

- **§13 `make index`.** AVeriTeC ranks within a claim's own pool, so retrieval
  builds a ~1000-document BM25 index, scores it and discards it in ~0.1 s. A
  persistent index would answer a different question than the benchmark asks.
  `make index` becomes real in Phase 4 (fact-check index) and Phase 5 (demo
  corpus).
- **§3 "every stage has at least two implementations"** now reads "by the phase
  that introduces its model". Phase 1 legitimately ships one implementation for
  stages whose model arrives in Phases 3–6.

### A regex bug the new FR-2 test caught immediately

The forward-artefact pattern listed `forwarded` before `forwarded\s+message`.
Regex alternation is left-to-right, so "Forwarded message: X" matched
`forwarded`, and the word "message" stayed glued to the claim. Every WhatsApp
forward carrying that header would have gone into retrieval and NLI with a
corrupted first token, and nothing would have looked broken.

Fixed in `src/preprocess/passthrough.py` by putting the longest alternative
first.

**The same bug exists in `src/data/normalize.py` and was deliberately NOT
fixed.** That function computes `text_sha1` for the frozen splits. Measured
impact: exactly **1 of 9,987** materialised texts starts with a forward
artefact, so the fix would change one hash — and one changed hash still
rewrites a committed split, invalidates `SPLITS.lock`, breaks the CI
reproducibility job and stales every results JSON built against it. A one-row
dedup miss is not worth that. `tests/test_normalize_frozen.py` now pins the
current behaviour and tells whoever changes it that they are signing up for a
split rebuild, not a code fix.

### MultiClaim, and what it unblocks

Access granted; the three CSVs were supplied manually and live in gitignored
`data/raw/multiclaim/` with their sha256 in `DOWNLOADS.json`. **Restricted and
not redistributable**, so only ID manifests are committed — the same rule as
AVeriTeC and X-CLAIM.

Bigger than the paper describes: **435,252 fact-checks, 89,139 posts, 105,424
pairs.**

| Language | Pairs | Posts |
| --- | --- | --- |
| English | 30,993 | 24,396 |
| Hindi | 11,271 | 8,376 |
| **Punjabi** | **104** | **91** |

**This closes Phase 2's hardest blocker.** The embedding comparison was
specified as "scored on retrieval", but AVeriTeC is English-only and X-CLAIM is
a span task with no relevance judgements — there was no multilingual retrieval
task to score anything on. A MultiClaim post is now a query and its paired
fact-checks are the gold, giving 3,153 dev and 3,156 test queries across the
three languages.

It also supplies something better than the planned synthetic romanisation:
**501 naturally romanized Hindi posts in train, 57 in dev, 53 in test** — real
people typing Hindi in Latin script, not transliterated output. The synthetic
X-CLAIM romanisation is still worth building, but this is the honest half of
the comparison.

**Punjabi remains the weak point**, and worse here than anywhere: 7 dev and 7
test posts. Any Punjabi claim-matching figure is a point estimate on single
digits and must be reported with its denominator, never as a bare percentage.

### Leakage: our split, so our bug to fix

The first MultiClaim build failed `make leakage` with dev↔test overlap. That is
handled differently from the AVeriTeC and X-CLAIM cases: those splits are
upstream's, so irreducible overlap is allowlisted in `KNOWN_LEAKAGE.json`
because removing it would alter a published benchmark. **MultiClaim ships no
splits — these are ours**, so overlap is a bug in the splitter, not something
to accept.

Fixed at the source, in three passes as each revealed the next:

1. Exact deduplication before splitting — 13 dev↔test pairs remained.
2. Near-duplicate clustering (union-find over a banded SimHash index, so 32k
   posts cost candidate pairs rather than half a billion comparisons) — 5 pairs
   remained, at Hamming 9–11.
3. Those five were a **threshold drift**: the clusterer gated at Hamming ≤ 8
   while the detector fails anything at Jaccard ≥ 0.90 out to Hamming 14,
   leaving a band the clusterer never considered. The clusterer now **imports**
   both thresholds from `src/data/leakage.py` instead of restating them, so
   "near duplicate" means one thing project-wide.

Final: 25,137 train / 3,153 dev / 3,156 test, `make leakage` clean across all
three datasets, and all 9 split files reproduce byte-for-byte from source.


## 2026-09-22 — CI fix, and the collection brief

Two smaller pieces of work that followed the MultiClaim commit.

### CI went red on MultiClaim, and the fix is a principle

The reproducibility job rebuilds every split from `data/raw/` and compares it to
`SPLITS.lock`. MultiClaim is access-restricted: its CSVs are gitignored, handed
over manually, and **can never exist on a CI runner**. The job crashed on a
missing `posts.csv`.

Loaders now declare their source files (`LOADER_SOURCES`), and the build skips a
dataset whose sources are absent instead of failing. `verify-reproducible`
reports those splits as unverifiable **by name** and checks the rest. Both halves
matter: it must not fail on data it cannot have, and it must not quietly pass as
though everything were verified.

One related guard: when a dataset is skipped, a full build no longer re-locks
`SPLITS.lock` — that would drop the skipped dataset's entries and turn an absent
source into deleted provenance.

Verified by simulating the CI condition rather than trusting it: 3 MultiClaim
files reported unchecked, the other 6 confirmed byte-identical, exit 0.
`tests/test_missing_sources.py` is the regression cover.

### docs/collection-brief.md

FR-26 needs ~100 romanized Hindi and Punjabi forwards typed by real people. It
is the one requirement in this project that cannot be automated, and MultiClaim
does not substitute for it: those 501 naturally romanized Hindi posts are public
posts, while the contribution is about messy personal typing.

The brief is written for the collectors, not for the repo, so it can be
forwarded as-is. It specifies the mix (including ~15 messages with **no**
checkable claim, to test that the system says "nothing to check" rather than
inventing a verdict), gives worked examples in both languages, and leads with
the instruction that actually matters: **do not correct your spelling** —
inconsistent romanization is the signal being measured, so a spellchecked set is
worthless.

Scheduled in Phase 2 by SRS traceability, but FR-26 reports the hand-typed set
*separately* from the synthetic transliterated one, so Phase 2 proceeds on the
synthetic half. **The binding deadline is Day 11**, before the final tables.


## Next

**Phase 2 — the language layer (Days 2-3).** fastText language ID, script
detection (already built), IndicXlit transliteration, the romanized eval sets,
the embedding comparison, and the t-SNE plot. Deliverable is the native vs
romanized table, which is the research contribution.

The retrieval task to score the embedding comparison on **now exists**:
MultiClaim, 3,153 dev / 3,156 test queries across en/hi/pa. That was the hardest
blocker and it is gone — MultiClaim is ingested, split, leakage-clean and
reproducible.

**Day 2 opens with the IndicXlit install spike, timeboxed to 30 minutes.**
`indic-transliteration` is already pinned and working, so Phase 2 is not
blocked either way; IndicXlit is an upgrade to measure against it on Dakshina.

Phase 1's floor to beat: retrieval Recall@10 = 0.0947, verdict macro-F1 =
0.2147. Retrieval is the bottleneck - improving the aggregator before
retrieval is tuning against noise.

### Open items

- **CheckThat! 2025 Task 2** — not started; needed for Phase 3.
- **Dakshina** (2.01 GB, confirmed reachable) — not downloaded; needed to
  evaluate transliteration in Phase 2.
- **fastText `lid.176`** — not downloaded; needed for FR-3 language ID.
- **Embedding models** for the Phase 2 comparison — BGE-M3, LaBSE, MuRIL,
  ~7.6 GB, not downloaded. Hub connectivity is intermittent, so expect retries.
- **Knowledge store train split** (63.52 GB) not downloaded. Dev is enough for
  Phase 1 and for evaluation; only needed if training retrieval on AVeriTeC.
- **A dense index over the full dev knowledge store is not feasible** on this
  GPU: 15.3 M passages, 31.3 GB of fp16 vectors, 14–28 GPU-hours.
  `SYSTEM_DESIGN.md` §7 budgets 3 GB. Use retrieve-then-rerank — BM25 to top-100
  per claim, dense over only those (~0.3 GB, ~15 min). **Settle this before
  Phase 5, not during it.**

### Needs a human — I cannot do these

- **~100 hand-typed romanized forwards (FR-26, P0).** See
  `collection-brief.md`; forward it as-is. Binding deadline **Day 11**.
  Punjabi is the priority — every dataset here is thin on it.
- **Native-speaker review of `app/static/i18n/{hi,pa}.json`** before any demo.
  Those strings are unverified placeholders, marked as such in the files.
- **Optional: set `HF_TOKEN`** before Phase 2 pulls ~7.6 GB of models. Raises the
  rate limit; will not help with dropped connections.

### Standing rules that are easy to forget

- Run `make leakage` after **any** data change.
- Never regenerate a committed split. If one looks wrong, stop and ask.
- Every experiment needs a dumb baseline in the same table.
- Before every experiment: what is the current number, what is the dumb
  baseline, and what would make this experiment invalid?
