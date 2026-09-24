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

**Eleven things that are easy to get wrong here:**

1. **Accuracy is close to meaningless on AVeriTeC.** Majority class scores 61%.
   Lead with macro-F1, always beside its baseline.
2. **The language column is not the script column.** Script is detected per row
   by `src/data/script_id.py`, never inferred from a filename or lang field.
3. **Never regenerate a committed split.** Frozen means committed. If one looks
   wrong, stop and ask — `make leakage` after any data change.
4. **CI has no torch.** Nothing under `src/` may import a model library at
   module scope; stages import lazily inside methods.
5. **The harness refuses rather than guessing.** If `make eval` exits 2, read
   the message — do not work around it. When it only *warns* (the sanity
   ceiling), do the check it names; Phase 2's 0.87 language-ID figure was
   verified that way rather than by raising the threshold.
6. **An aggregate will hide the finding.** Every headline number here is
   dominated by English or native script. The per-script breakdown is where the
   result is: fastText looks *worse* than a free script check overall (0.9756 vs
   0.9813) and is 0.3158 vs 0.0000 on the cell that matters.
7. **Two environment traps.** `fasttext-wheel` 0.9.2's `predict()` raises under
   NumPy 2, so `src/preprocess/lid.py` calls the C++ predictor directly — do not
   "simplify" it back. And `uv` has gone missing from this machine once; the
   venv keeps working, so nothing fails until something needs installing.
8. **A measurement bug looks exactly like a weak model.** Phase 3 produced two,
   and both read as "the model barely beats its baseline and the ablation shows
   nothing": a stage gate suppressing the stage being measured, and scoring a
   tagger through a round-trip that caps and back-fills. Neither raised an
   error. What caught both was having an earlier number on record to disagree
   with. So: **score the baseline before building the model, keep every
   intermediate figure, and when a number moves, find out why before believing
   it.** A flat result is a hypothesis about the code, not just about the model.
9. **`gh` exists but is not on PATH** — `C:\Program Files\GitHub CLI\gh.exe`.
   CI was red for three commits once because it was assumed unavailable rather
   than looked for.
10. **A convenient eval set can rank models backwards.** FR-6's derived
    check-worthiness set and the 100 hand-typed forwards disagree about which
    arm is better, in both directions: the trained classifier scores 0.7222 on
    the derived set and 0.4536 on the real one, the zero-shot arm 0.5478 and
    0.5938. Model selection on the convenient set picks the arm that fails.
    Any set built by construction rather than collection has to prove it
    correlates with the real one before it is used to choose anything.
11. **The numbers have been right and their labels wrong, twice.** Both times a
    copy-pasted table row or config note stayed plausible. Auditing a write-up
    means reading every figure back to the results file AND checking the prose
    that says what produced it.

**To get running:** `make setup` then `make test`. The environment is already
built on this machine (Python 3.11 via uv, CUDA torch, models cached on `D:`).

---

## Status at a glance

| | |
| --- | --- |
| **Current phase** | **Phase 3 COMPLETE**, gaps and all. Both requirements measured against baselines, the X-CLAIM ablation replicated, and the four verification gaps closed 2026-09-24. Next is Phase 4. |
| **Clock** | 14 days. **Days 1-4 done** (Phases 1-3). Day 5 = Phase 4. Freeze end of Day 12. |
| **Hardware** | i7-14700HX + RTX 4050 laptop GPU, 6 GB VRAM. No Colab. |
| **Branch model** | Trunk-based. Everything commits straight to `main`. |
| **Python** | 3.11.16 via uv, in `.venv`. System Python is 3.13 and is not used. |
| **Tests** | 322 passing, 2 skipped, 2 gpu-deselected |
| **Datasets in hand** | AVeriTeC, X-CLAIM, MultiClaim, handtyped (FR-26), Dakshina, **CheckThat! 2025 T2** |
| **Datasets waiting** | None. Every dataset is downloaded, split, locked and leakage-checked. |
| **GPU stack** | torch `2.9.1+cu128`, CUDA available on the RTX 4050. ~4.9 GiB usable VRAM. |
| **Models trained** | Romanized LID, in-domain Word2Vec, and **6 XLM-R+LoRA adapters** (5 span ablation arms + check-worthiness). |
| **Numbers so far** | Span token-F1 **0.7463** (baseline 0.6851) · claim matching MRR 0.5244 · LID ~0.86 on the hand-typed set · transliteration CER 0.4281 · AVeriTeC verdict macro-F1 0.2147. **FR-6 partially solved by the ZERO-SHOT arm**: macro-F1 0.5938 vs 0.4595 majority, 7/15 real negatives caught -- at the cost of rejecting 18 of 85 real claims. The trained classifier catches 0/15. |
| **CI** | Green, checked with `gh run list` after every push (last: `c250304`). A sha here goes stale the moment the next commit lands -- check, do not trust. Runs take ~1m50s. `gh` is at `C:\Program Files\GitHub CLI\gh.exe`, NOT on this shell's PATH. |

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


## 2026-09-23 — Phase 2: the language layer, and what romanization does to an embedding

Days 2-3 in one sitting. Everything below is measured through `make eval`; the
config hashes are in `results/` and the tables in `docs/results.md`.

### The hand-typed forwards arrived early

100 rows, against a Day 11 deadline. Clean: UTF-8 with no encoding damage, no
duplicates, 15 deliberate no-claim rows, and **33 Punjabi rows carrying a
matched Gurmukhi rewrite of the same message**. Leakage-clean against all four
datasets.

Two decisions worth recording. Seven rows were declared `lang=mixed`, which the
split schema does not have and `SYSTEM_DESIGN.md` §4 refuses to add for the same
reason it refuses a `mixed` *script* value: code-mixing is continuous and
`script_purity` already reports it, while a fourth category would add a cell to
every breakdown the contribution rests on. Each was assigned its dominant
language **by hand, by grammatical marker rather than vocabulary** — English and
Hindi nouns are shared, case markers and verb endings are not — with the
declaration kept in `notes`. Done by hand deliberately: deriving them from
fastText would have made them useless as gold for scoring fastText. `hw012` is
the one close call and is recorded as such in `loaders.MIXED_UNCERTAIN`.

They are `dev`, not `test`. A measurement set that lives behind
`TRUTHLENS_ALLOW_TEST=1` cannot be looked at while building, which is the
opposite of what this set is for. Nothing trains on them.

### FR-3: fastText cannot do the one thing this project needs

`lid.176` scores **0 of 100** on the hand-typed forwards — 43 called English, 57
refused, none correct. On MultiClaim's naturally romanized Hindi it manages
0.3158.

The aggregate hides this completely. On MultiClaim overall fastText scores 0.9756
against a *free script check's* 0.9813, which reads as "fastText is worse". It
is not: 94% of that split is English or native-script Hindi, which the alphabet
already answers. Everything that matters is in two small cells.

| accuracy | script | fastText | hybrid |
| --- | --- | --- | --- |
| MultiClaim hi/latn (n=57) | 0.0000 | 0.3158 | **0.7368** |
| MultiClaim overall (n=3153) | 0.9813 | 0.9756 | 0.9892 |
| hand-typed (n=100) | 0.0000 | 0.0000 | **0.8500** |

The hybrid keeps `lid.176` in front — it is genuinely excellent at *rejecting* a
language we do not support, French at 0.992 — and puts a character n-gram
classifier behind it. Characters, not words: romanized Hindi and Punjabi are not
separable by vocabulary, since both borrow from English and forwards code-mix
constantly, but they are separable by endings (`-nde`, `-diyan`, `nu`, `te`
against `-ta hai`, `-ne`, `ko`), which are 3-to-5 character patterns.

**Dakshina is what made Punjabi work.** Our train splits hold 42 genuinely
romanized Punjabi rows; Dakshina adds ~4,700. Punjabi on the hand-typed set went
5/36 → 29/36. Dakshina ships only dev and test, so its **test** half trains the
classifier and its **dev** half is reserved for transliteration evaluation — no
row is both trained on and evaluated on, for any task.

The harness fired its sanity ceiling at 0.87 and the right response was to do the
check it asks for, not to raise the threshold: **0 of the 100 rows appear
verbatim or as a substring anywhere in the training pool**, which reads
`train.jsonl` files only and never opens a dev file. The ceiling is now set
per-config with that justification written beside it.

### FR-5: the failures compound

Transliteration only fires when language ID says `hi` or `pa`. Language ID
failed on exactly the inputs that need transliterating, so for a while the
measured "transliteration" number was the identity baseline to four decimal
places — the stage had never run once.

| 33 matched Punjabi pairs | CER | WER |
| --- | --- | --- |
| identity (do nothing) | 0.8518 | 0.9290 |
| rule-based, fastText routing | 0.8518 | 0.9290 |
| rule-based, hybrid routing | **0.4281** | 0.7253 |
| rule-based, oracle language | 0.3810 | 0.7130 |

`force_lang` exists to separate the two, or FR-5's number would really be FR-3's.
The remaining 0.047 to the oracle is the cost of the 7 Punjabi rows LID misses.

The rule-based transliterator's limit is sharp and worth stating: a word-FINAL
vowel is recoverable (`sach` → सच, `kaha` → कहा), a word-MEDIAL long vowel is
not (`sarkar` → सरकर, never सरकार) because choosing needs a lexicon.

### IndicXlit: ruled out, and not for the expected reason

The spike finally ran once `uv` was reinstalled, and failed in 43 seconds.
fairseq 0.12.2 needs MSVC build tools — fixable — but resolving
`ai4bharat-transliteration` also pulls **tensorflow 2.21, tf2crf, urduhack and
torch 2.14, the CPU build**, which would silently replace the CUDA torch every
other stage depends on. A transliterator must not cost the project its GPU.

### The embedding ladder

3,153 MultiClaim dev posts against **78,077 fact-checks** — every fact-check in
at least one annotated pair, the MultiClaim / SemEval-2025 Task 7 setup. Not the
3,943 the dev queries point at: retrieving only from documents that are already
somebody's answer is not retrieval.

| rung | MRR | R@10 |
| --- | --- | --- |
| random floor | 0.0002 | 0.0008 |
| Word2Vec (in-domain) | 0.0915 | 0.1197 |
| MuRIL | 0.1127 | 0.1369 |
| TF-IDF | 0.2311 | 0.3045 |
| LaBSE | 0.3216 | 0.4170 |
| **BGE-M3** | **0.5244** | **0.6688** |

**TF-IDF beats Word2Vec and MuRIL.** Without the lexical rung in the table,
MuRIL's 0.1127 would have read as a result rather than a warning. This is
exactly what CLAUDE.md's baseline rule is for.

TF-IDF's average is itself misleading: 0.3901 Recall@10 on English, **0.0521 on
Devanagari**. A Devanagari post and a mostly-English fact-check corpus share no
characters at all. That pair of numbers is the clearest possible argument for
why this project needs embeddings.

Three correctness points that were worth the extra code:

- `random_rank` was drawing candidates from the **gold** ids — a lottery among
  correct answers, not a floor. Configs now name `corpus_ids` and the baseline
  draws from the same 78,077 the model searched, which moved the floor to MRR
  0.0002.
- BGE-M3 is **CLS-pooled**, not mean-pooled. It is trained contrastively on the
  CLS position; mean pooling measures something it was never optimised for and
  is an easy way to conclude the best model is the worst.
- TF-IDF is **fitted state, not weights** — the vectoriser and SVD basis *are*
  the vector space — so it is saved beside the index it built.

### The native vs romanized table — the deliverable

MRR, Hindi, n=737 native / 57 romanized:

| rung | native | romanized | gap |
| --- | --- | --- | --- |
| TF-IDF | 0.0379 | 0.0877 | **-0.0498** |
| Word2Vec | 0.0618 | 0.0581 | 0.0038 |
| MuRIL | 0.1218 | 0.0439 | 0.0779 |
| LaBSE | 0.3648 | 0.1926 | 0.1722 |
| BGE-M3 | 0.4981 | 0.3585 | 0.1396 |

Romanized Hindi runs at **72% of native** under BGE-M3. TF-IDF's gap is
*negative* — romanized scores better than Devanagari — because romanized Hindi
shares Latin characters with a largely English corpus while Devanagari shares
none. The only rung where romanizing helps, and for a reason unrelated to
understanding.

The gap metric had to be fixed before this table meant anything. For language ID
the breakdown cells are split by language and the classes *are* languages, so
every cell holds one gold class and its macro-F1 is pinned at 1/n_classes
however right the model is. Per-cell accuracy is the honest measure there.

Punjabi is n=7 and n=2. The harness flags both `low_n`, which is correct, and
every Punjabi figure is reported as a fraction.

### FR-27, and the finding that should drive Phase 3+

The t-SNE figure showed romanized Hindi and romanized Punjabi sitting on top of
each other, away from their own native-script twins. Measured rather than
eyeballed — mean cosine between **unrelated** sentences under LaBSE:

    unrelated hi-native    vs unrelated pa-native       0.3773
    unrelated hi-native    vs unrelated hi-romanized    0.3856
    unrelated pa-native    vs unrelated pa-romanized    0.4553
    unrelated hi-ROMANIZED vs unrelated pa-ROMANIZED    0.6900   <--

Two sentences with nothing in common, in two different languages, score 0.6900
because both are written in Latin letters. The *same* sentence in native and
romanized form scores 0.5613. **Romanization forms a cluster of its own, and it
is a stronger signal than content.** That is the mechanism behind the retrieval
gap, stated as a number instead of a hypothesis.

It predicts the fix and then rules out the cheap version. Transliterating out of
Latin script should help — but doing it with the rule-based transliterator
*hurts*: Recall@10 on the hi/latn cell falls **0.1988 → 0.1199**, because a CER
of 0.38 lands the query in the wrong place. So **an accurate transliterator is
the highest-value thing to build next**, and transliteration output should be
shown to the user, not fed to retrieval, until it is.

One caveat recorded so it cannot be misread: the hand-typed pairs score a
*higher* native-vs-romanized cosine (0.7942) than Dakshina's (0.5613-0.6298).
That is not evidence that real typing is easier. It is code-mixing — "KYC",
"UPI", "48" survive verbatim into the Gurmukhi version and anchor the two
embeddings together. Shared-Latin-token overlap is 0.0513 for the hand-typed
pairs against 0.0119-0.0173 for Dakshina, and is now recorded beside every
cosine in `docs/figures/tsne_parallel_claims.json`.

### Three bugs, all caught by something refusing rather than guessing

- **`fasttext-wheel` 0.9.2 is broken under NumPy 2.** Its `predict()` ends in
  `np.array(probs, copy=False)`, which NumPy 2 raises on. Every call was
  throwing, `LanguagePreprocess` was catching it and falling back to the script
  heuristic, and **the fallback looked exactly like a result** — the first
  "finding" of the day was the fallback, not fastText. `lid.py` now calls the
  C++ predictor directly, and `batch.py` prints a loud warning when any row ran
  degraded.
- **Language ID scanned the top-5 for a supported language**, so confidently
  French text came back as English. Takes the top prediction only.
- **`majority_class` read `label` while being scored against `lang`.** Caught
  only because the two label sets are disjoint.

And one design bug: `build_splits` wrote an empty `train.jsonl` for an eval-only
dataset and locked it. "An empty train split exists" is a different claim from
"this dataset has no train split".

### Environment

`uv` had vanished from this machine entirely — the venv still worked, so nothing
failed until something needed installing. Reinstalled (0.12.18); `gensim` 4.4.0
added to `requirements-ml`; torch verified still `2.9.1+cu128` afterwards.

Measured on the RTX 4050, encoding 78,077 fact-checks: **BGE-M3 12.1 min (peak
1.11 GiB), LaBSE 2.4 min, MuRIL 3.7 min**, against 4.96 GiB free. The "long
pole" risk flagged in the Phase 2 plan did not materialise.

## 2026-09-24 — CheckThat! 2025 Task 2 downloaded; two docs were wrong about it

Phase 3's only dataset gap, closed. Wired into `scripts/download_data.py` beside
AVeriTeC and X-CLAIM rather than fetched by hand, so all twelve files' sha256s
are in `DOWNLOADS.json` and a Phase 3 number can be traced to exact bytes.

**It needs no registration.** `docs/specs/SRS.md` called it a "Research release"
and `data/CLAUDE.md` said "Requires registration". Both were wrong -- it is a
plain public GitLab repo. Corrected in place, and the correction is worth more
than the data: an unchecked "you need permission for this" note is how a
dataset stays unacquired for a week.

en/hi/pa only, matching the X-CLAIM policy. English is taken because X-CLAIM's
own finding is that joint multilingual training beats zero-shot transfer, and
reproducing that needs the English half.

| split | en | hi | pa |
| --- | --- | --- | --- |
| train | 11,374 | 1,081 | **445** |
| dev | 1,171 | 50 | 50 |
| test (gold) | 1,285 | 100 | 100 |

**445 Punjabi training rows is the most Punjabi supervision this project has**,
ahead of X-CLAIM's ~346 and unlike MultiClaim's 7 dev posts it is a real
training set.

Two things found by looking at the files rather than trusting the filenames.

**The test split ships without answers.** `test-*.csv` has a `post` column only;
the labels are in `test-outputs/task2_*_gold.csv` under a different naming
convention. Both are downloaded, and `test_gold-*.csv` is the superset -- same
posts, plus the normalized claim. A loader that reaches for `test-*.csv` will
get a file with no gold in it and no error.

**The language column is not the script column, for the third dataset running.**
`train-pa.csv` is 300 Gurmukhi, 74 Devanagari and 71 Latin -- only 67% of the
"Punjabi" file is actually in Punjabi's script. `train-hi.csv` carries 71 Latin
rows, and even `train-eng.csv` has 139 Devanagari ones. `src/data/script_id.py`
handles this already; the point is that the gotcha keeps being real.

Those 142 genuinely romanized hi/pa rows are also **more real romanized training
data for the language-ID classifier**, which currently has only 42 real Punjabi
rows plus Dakshina. Retraining on them would likely improve FR-3 further, but it
would move a number that is already measured and reported, so it belongs in
Phase 3 as a deliberate step with a before-and-after, not as a quiet rebuild.

Not built yet: the loader and the frozen splits. That is Phase 3 work.

## 2026-09-24 — CheckThat! ingested, and a cross-dataset leak that was there all along

Ingesting CheckThat! 2025 Task 2 turned up a leak between datasets that the
project's leakage machinery could not see, because it only ever looked *inside*
one dataset at a time.

### The leak

CheckThat! Task 2 and X-CLAIM are built from an overlapping pool of
fact-checked social posts. Measured, both directions:

| | n | severity |
| --- | --- | --- |
| checkthat/train ∩ x_claim/train | 4,799 | harmless: train to train |
| checkthat/train ∩ x_claim/dev | 497 | **leak** |
| **x_claim/train ∩ checkthat/dev** | **400** | **leak — 32% of that dev set** |
| x_claim/train ∩ checkthat/test | 375 | **leak** |
| checkthat/dev ∩ x_claim/dev | 181 | eval to eval: correlated, not contamination |

The one that mattered: **400 of CheckThat's 1,244 dev posts sat in X-CLAIM's
train split.** Phase 3 plans a jointly-trained XLM-R over both, so the
normalization dev number would have been largely memorisation.

`make leakage` never saw it. "Train yields to eval" was applied within each
dataset, which was sufficient right up until two datasets shared a post pool.

### The fix, and what it cost

Same rule, wider scope: a row in ANY eval split is dropped from EVERY train
split. `load_external_evals()` in `scripts/build_splits.py` reads every other
dataset's committed dev/test before deduplicating, and
`tests/test_no_leakage.py` now asserts the property directly rather than
trusting the builder.

| split | before | after |
| --- | --- | --- |
| checkthat/train | 12,900 | 8,318 |
| x_claim/train | 5,430 | 4,398 |
| multiclaim/train | 25,228 | 24,642 |
| every dev and test | — | **byte-identical, verified against git** |

X-CLAIM lost 16.3% of its training data. That is the price of the alternative
being a number nobody could defend. No eval split moved, so every published
benchmark stays comparable and no `results/*.json` was invalidated by the split
change itself.

### What DID have to be re-measured

Two models train on the changed splits, so both were retrained and rescored in
this commit. The shifts are small and no conclusion moves:

| | before | after |
| --- | --- | --- |
| LID, hand-typed forwards | 0.8700 | **0.8500** |
| LID, MultiClaim overall | 0.9908 | **0.9892** |
| LID, MultiClaim hi/latn | 0.7719 | **0.7368** |
| Word2Vec rung, MRR | 0.0920 | **0.0915** |
| transliteration CER | 0.4281 | **0.4281** (unchanged) |

**The hand-typed figure is not stable to three decimal places, and should not
be quoted as though it were.** Across four retrains today, driven only by
changes to the TRAINING pool and never to this eval set, it read 0.8700,
0.8600, 0.8800 and 0.8500. That is a swing of three rows out of 100. Report it
as **~0.86 on n=100**, and lead with the MultiClaim hi/latn cell (0.7368,
n=57) where the denominator is larger and the number is steadier. What is not
in doubt is the comparison: the two baselines score 0.0000 on this set, and
they do so by construction rather than by luck.


The transliteration number did not move because the one hand-typed row language
ID now gets wrong is not among the 33 that carry a Gurmukhi reference.

Everything else on the ladder is untouched: TF-IDF fits on the fact-check
corpus, and MuRIL, LaBSE and BGE-M3 are pretrained. Their config hashes changed
anyway, because the hash covers `SPLITS.lock` and the lock moved. Rerun, same
numbers, and `p1_bm25_retrieval` was re-chained to the new
`p1_random_retrieval` hash.

### CheckThat's own leakage is upstream's, and stays

30 dev-to-test pairs, 2.0% of its test set. Allowlisted per-uid in
`KNOWN_LEAKAGE.json` rather than fixed, because removing rows from a published
shared-task eval split would make our numbers incomparable with the lab's. This
is the DS@GT CheckThat! 2025 finding `build-plan.md` cites, reproduced directly
on the 2025 data. Text is deliberately omitted from those entries -- 30 pairs is
more source text than a committed file should carry.

### A smaller thing the same pass exposed

`freeze_split` logged a changelog entry for any write to a tracked file, and
rebuilding a dataset re-freezes all of its splits -- so dev and test were
recorded as having moved when they had not. The changelog's own header says an
entry means prior results are no longer comparable, which made those entries
actively misleading. `freeze_split` now compares bytes first and does not log a
no-op. The wrong entries are corrected in place by a further entry rather than
deleted: an append-only log that gets edited is not an audit trail.

### Punjabi

CheckThat! contributes **368 Punjabi training rows** (254 Gurmukhi, 50 Latin, 64
Devanagari) -- and once again the language column is not the script column: only
67% of the "Punjabi" file is in Punjabi's script.

## 2026-09-24 — Phase 3: the front of the pipeline, and what FR-6 actually needs

> **Corrected 2026-09-24.** Two rows of the ablation table below were originally
> taken from superseded scoring runs, and one finding drawn from them was wrong.
> The table here has been fixed in place because the figures were simply
> incorrect rather than a reversed decision; what happened, and the finding that
> replaced the wrong one, is in the correction entry further down.
>
> **Superseded in part, 2026-09-24.** The FR-6 section below concludes that
> check-worthiness is unsolved. That held for every arm that had been run at the
> time; the zero-shot NLI arm, built two entries down, catches 7 of 15 real
> negatives and beats the majority baseline. The diagnosis below is what led to
> it and is left intact — read the later entry for where FR-6 actually stands.

Two requirements, three models trained, and two of the phase's most useful
outputs are negative results.

### FR-7 span identification: the ablation replicates X-CLAIM's finding

XLM-R-base + LoRA, 887K trainable of 278M (0.32%), 3 minutes and 2.59 GiB peak
on the 4050. Token F1 on X-CLAIM dev:

| arm | overall (600) | en/latn (392) | hi/deva (96) | pa/guru (76) |
| --- | --- | --- | --- | --- |
| whole_post_span | 0.6851 | 0.6647 | 0.7385 | 0.7445 |
| mono-en | 0.7106 | 0.6911 | 0.7089 | 0.8027 |
| mono-hi | 0.7053 | 0.6507 | **0.7881** | 0.8352 |
| mono-pa | 0.7175 | 0.6990 | 0.7375 | 0.7953 |
| zero-shot | 0.7370 | 0.7055 | 0.7811 | **0.8426** |
| **joint** | **0.7463** | **0.7232** | 0.7805 | 0.8382 |

Joint beats every monolingual arm, which is what `build-plan.md` asked to be
replicated deliberately rather than rediscovered. Three things worth more than
the headline:

**The baseline is harder to beat in Indic than in English** — 0.7445 for
pa/guru against 0.6647 for en/latn, because Indic posts here are more
claim-dense. The model faces its highest bar in exactly the languages where it
has least data: 249 Punjabi rows against a 0.7445 floor, 2,918 English rows
against 0.6647. That inverts the naive reading.

**Zero-shot ties joint on Punjabi** (0.8426 vs 0.8382, n=76, comfortably inside
noise) having never seen a single Punjabi training example. Adding 249 Punjabi
rows to en+hi bought essentially nothing. Punjabi performance here is almost
entirely cross-lingual transfer, not Punjabi supervision — which is a more
useful finding than "joint wins", because it says where effort should NOT go.

**Punjabi is better served by HINDI training data than by Punjabi.** mono-hi
scores 0.8352 on pa/guru against mono-pa's 0.7953, on 1,158 Hindi rows versus
337 Punjabi ones — across a script boundary, Devanagari to Gurmukhi. Together
with the zero-shot result, the picture is consistent: for Punjabi span
identification here, related-language data beats in-language data at this scale.

**mono-hi is the best arm on Hindi** (0.7881 vs joint's 0.7805). Joint training
wins on average and on English, but it is not uniformly better per language —
worth stating, because "joint wins" is the headline and this is the asterisk.

The fourth arm the build plan names — training on machine-translated English —
is not run. `data/CLAUDE.md` never downloaded `en2xx` precisely so it could not
contaminate this comparison. An absence with a recorded reason, not a gap.

### FR-6 check-worthiness: not solved, and now we know exactly why

The first attempt read check-worthiness off the span model: no claim tokens, no
claim. It rejected **0 of 15** no-claim messages on the hand-typed set while
getting 70/70 straightforward positives right.

The reason is structural, not a threshold. **The span model trains on X-CLAIM,
where every post contains a claim.** It has never seen the negative class and
has no way to answer in the negative. A model cannot learn a class it was never
shown.

So check-worthiness became its own sequence classifier, trained on the derived
`xclaim_cw` set (7,874 rows, 3,402 negatives). It learns the task and does not
transfer:

| | macro-F1 | vs majority | negatives caught |
| --- | --- | --- | --- |
| derived dev (n=963) | **0.7222** | +0.3383 | 190/363 = 52.3% |
| hand-typed (n=100) | 0.4536 | -0.0059 | **0/15** |

That gap was predicted in the loader docstring before it was measured, and the
prediction was right. Derived negatives are out-of-span fragments of posts that
DID contain a claim: they read as truncated mid-thought. A real blessing —
"Sat Sri Akal ji, Rabb sabnu khush rakhe" — is fluent, complete, and asserts
nothing. Different problems, and training on one does not touch the other.

The rules baseline ties majority class exactly on the hand-typed set (macro-F1
0.4595, 0/15 negatives). Rules catch short or empty messages; they cannot catch
"wordy but asserts nothing". I stopped tuning at that point rather than fit six
hand-picked examples, and pinned the limitation in a test that fails loudly if
a future change fixes it.

**Category breakdown on the hand-typed set, which its collection brief designed
for exactly this:**

| category | found |
| --- | --- |
| straightforward check-worthy | 70/70 |
| buried claim in a long emotional message | 9/15 |
| no claim at all | 0/15 |

Rejected messages average 173 characters against 91 for accepted ones — the
model degrades precisely on the buried-claim category the brief asked for.

**So the highest-value human task left is ~100 more real no-claim messages.**
The 15 collected are the only reason we know FR-6 is unsolved, and are far too
few to train on. This is now the top item under "needs a human".

### Normalization is not extractable, and that is measurable

chrF 0.2835 against a longest-sentence baseline of 0.2875 — extraction loses to
a `split('.')`. Not a tuning problem:

| | |
| --- | --- |
| gold claims appearing VERBATIM in the post | 55/1271 = **4.3%** |
| mean share of gold words present anywhere in the post | 48.4% |
| golds with under half their words in the post | 665/1271 |

The CheckThat references describe what a post CLAIMS; they do not quote it.
Post: "The Karnofsky Jewish family, who immigrated from Lithuania, employed a
7-year-old..."  Gold: "Photo shows Louis Armstrong as a child".

That settles the Phase 6 abstractive case with a number rather than an
intuition, which is what D2 of the phase plan said it was for.

### Two measurement bugs, both of which produced publishable-looking numbers

**The FR-6 gate was suppressing FR-7's extractor.** Running check-worthiness
before extraction is correct for the served pipeline, but it rejected 59 of 600
X-CLAIM dev rows and every one then scored as an all-`O` prediction. The joint
arm fell 0.7469 to 0.6801 without the span model changing at all. `--gate` is
now explicit and off by default: span and normalization measure FR-7,
check-worthiness measures FR-6. Two questions, two measurements.

**Scoring the tagger through `extract()` cost precision.** `extract()` caps at
MAX_CLAIMS and falls back to the whole post when it finds nothing — both right
for PRODUCING claims, both wrong for scoring a tagger. Raw tags score
P 0.7747 / R 0.7199 / F1 0.7463; the same model round-tripped scores
P 0.6284 / R 0.7998 / F1 0.7038.

Both bugs produced a flat ablation clustered near the baseline, which reads as
"the model barely works and joint training does not help" — a conclusion that
would have been written up. **What caught them was having the earlier ungated
number on record to disagree with.** A new number is only obviously wrong when
there is an old one to contradict it, which is the argument for scoring
baselines first and keeping every intermediate figure.

A third near-miss: `--claims-impl xlmr` hardcoded the joint adapter, so all four
ablation arms would have scored identically — and identical arms read as "the
ablation shows no difference" rather than "the script never loaded the other
three models". `--adapter` now routes through `stage_args`.

### Smaller things

`MAX_CLAIMS` is enforced in the orchestrator rather than trusted to extractors.
FR-7's "at most 3" is a promise the API makes, and each extra claim costs a full
retrieval and NLI pass, so an over-producing extractor is expensive as well as
wrong. It had drifted into three copies across `src/claims/` and now lives once
in `contracts.py`, where the `Claim` contract is.

The harness gained `task: span` (token P/R/F1 over claim tokens, plus exact-span
match) and `task: normalization` (chrF + exact match), both following the Phase 2
transliteration seam list. `O` is deliberately not scored as a class: about half
of every X-CLAIM post is not the claim, so an all-`O` prediction would otherwise
look respectable while finding nothing. chrF rather than the shared task's
METEOR, because METEOR's synonym matching is English-only via WordNet and an
English METEOR cannot share a column with a Punjabi one.

The X-CLAIM span end index is **inclusive**, measured rather than assumed:
`== len(tokens)` occurs 0 times across the corpus, `== len(tokens) - 1` occurs
2,897. `scripts/build_span_gold.py` re-checks it on every build and refuses if
it flips, because getting it wrong shifts every span by one token while still
looking entirely plausible.

## 2026-09-24 — Correction: two rows of the Phase 3 ablation were from superseded runs

Caught by the pre-compaction audit, which cross-checks every figure in the docs
against the `results/*.json` it came from.

The ablation was scored three times: once with the FR-6 gate wrongly suppressing
the extractor, once round-tripped through `extract()`, and once correctly. The
table written into the Phase 3 entry took `mono-en` from the FIRST run and
`mono-hi` from the SECOND. Four of six rows were right, which is why it read as
plausible.

| arm | was | is |
| --- | --- | --- |
| mono-en overall | 0.6685 | **0.7106** |
| mono-hi overall | 0.6970 | **0.7053** |

**One stated finding was wrong and has been removed:** "mono-en scores below the
baseline — training on English alone is worse than predicting the whole post."
It is not. **No arm is below the baseline.** The correct numbers support a
better finding in its place: mono-hi scores 0.8352 on Punjabi against mono-pa's
0.7953, so for Punjabi span identification at this scale, related-language data
beats in-language data — and mono-hi beats joint on Hindi (0.7881 vs 0.7805), so
joint training wins on average without being uniformly better per language.

The commit message of `7e13e81` still carries the wrong table. History is not
rewritten here; this entry is the correction, and `docs/results.md` is generated
from `results/` so it was never wrong.

**Why this happened, and the cheap guard against it.** Three scoring passes in
quick succession, numbers copied into prose from terminal scrollback rather than
from the results files. The guard is mechanical and takes seconds: before
publishing any table, re-read every figure out of `results/*.json` by
`experiment` name and assert it appears in the doc. That check found this in one
run, and it is the same check that caught three wrong figures in the Phase 2
docs. It should run before every phase write-up, not only before a compaction.

## 2026-09-24 — The four Phase 3 gaps closed, and FR-6 is no longer unsolved

All four items from the previous section are built. The one that mattered
changed a published conclusion, which is why it was ranked first.

### FR-6: the zero-shot arm beats the baseline where the trained one does not

`src/claims/nli_zeroshot.py`, registered as `claims=nli`. No training at all:
the Phase 1 mDeBERTa-XNLI model with the hypothesis pinned to *"This message
states a fact that can be checked."*, premise being the forward, and
`P(entailment) >= 0.5`. `NLIStance` is reused rather than reimplemented, so it
inherits that class's id2label check — a model whose labels were ordered
differently raises instead of silently inverting every decision.

| arm | derived dev (n=963) | hand-typed (n=100) | real negatives caught |
| --- | --- | --- | --- |
| majority_class | 0.3839 | 0.4595 | 0/15 |
| heuristic (rules) | 0.4217 | 0.4595 | 0/15 |
| xlmr (trained classifier) | **0.7222** | 0.4536 | **0/15** |
| **zero-shot NLI** | 0.5478 | **0.5938** | **7/15** |

**7 of 15, up from 0 of 15**, and macro-F1 0.5938 against the majority
baseline's 0.4595 — the first arm in this project to beat that baseline on the
hand-typed set. FR-6 moves from *unsolved* to *partially solved, with a stated
cost*.

The cost is real and belongs beside the headline: **18 of 85 genuine claims are
also rejected** (precision on `No` is 0.28, recall on `Yes` falls to 0.79).
One in five real claims would be answered "there is nothing to check here",
which is the worst failure this product has — worse than a wrong verdict,
because it is silent. The threshold is the knob; it was left at the untuned
0.5 for the reason below.

**The reason it works is the reason the trained arm failed.** The trained
classifier learned `xclaim_cw`'s distribution, where negatives are out-of-span
remainders that read as truncated mid-thought. A zero-shot model has no
distribution of ours to be skewed by, and "does this text assert that?" is
XNLI's whole task. The prediction written into the Phase 3 entry — that this
was the approach most likely to work — held.

### The two eval sets rank the two arms in opposite orders

This is the more transferable finding.

| | derived dev | hand-typed |
| --- | --- | --- |
| trained xlmr | 0.7222 | 0.4536 |
| zero-shot NLI | 0.5478 | 0.5938 |

Selecting on the derived set picks the arm that fails on real data, by a wide
margin in both directions. The derived set is not merely noisier than the real
one — it **anti-correlates** with it on the only comparison made so far. That
is exactly what the Phase 3 loader docstring warned would happen, and it is now
a measurement rather than a caution.

Two consequences, both acted on:

- **The threshold was not tuned.** The plan allowed choosing it on the derived
  set. Having measured that this set ranks arms backwards, tuning an operating
  point on it would be optimising against the wrong target, so the reported
  figure uses the untuned 0.5. The `--cw-threshold` flag exists for when there
  is a real set large enough to choose on.
- **The ~100 more real no-claim messages stay the top human task**, and the
  argument for them is now stronger, not weaker: there is finally an arm whose
  operating point is worth choosing, and 15 negatives is not enough to choose
  it with.

Stated limitation: the hypothesis is English and these messages are romanized
Hindi and Punjabi, which XNLI covers only in Devanagari. 0.5938 is a floor for
the method, not its ceiling.

### The other three gaps

**`tests/test_loader_xclaim.py`** — 15 tests pinning the inclusive-end span
convention. Two layers on purpose: pure tests that run in CI and pin what the
code DOES with the convention (the token at `end` is inside the span; a row
claiming `end == len(tokens)` is refused rather than clipped; the derived
negative excludes the whole claim), and corpus tests that re-measure the
evidence and skip where `data/raw/x_claim/` is absent. The builder's guard is
now tested by fabricating an exclusive-indexed corpus and checking it refuses —
previously the guard existed but nothing proved it was armed.

**VRAM figures into `docs/environment.md`** — `SYSTEM_DESIGN.md` §10's "~2.8 GB
resident" was an estimate nobody had checked. It is right: the heaviest run
peaks at **2.588 GiB**. Two things the table shows that the estimate could not
— peak VRAM is **flat in dataset size** (337 rows and 7,874 rows both peak near
2.58 GiB, because it is set by batch × sequence length), and training peaks
about 1.5 GiB above the heaviest inference workload, so **training is the
binding constraint on this card, not serving**. The LoRA checkpoint policy (D6
of the plan) is written down in the same section, which was also never done.

**Tests for `src/claims/span_xlmr.py`** — `spans_from_tags` across 9 tag
sequences including the malformed ones a model actually emits, the
`AdapterUnavailable` refusal, and `extract()`'s cap and whole-post fallback,
with the fallback pinned specifically because `pipeline.batch._span_tags`
bypasses it and the two must stay distinguishable.

Suite: **322 passing**, 2 skipped, 2 gpu-deselected, up from 283.

### Three check-worthiness configs were misattributing their own implementation

Found while adding the new configs, and the same class of error as the ablation
rows: `p3_cw_handtyped_xlmr.yaml` and `p3_cw_derived_xlmr.yaml` both carried
copy-pasted `notes` reading *"Implementation: claims=heuristic (rules only, no
weights)"*, and both `_derived_` configs carried a header block describing the
hand-typed set. A reader of `docs/results.md` would have attributed the trained
classifier's 0.7222 to the rules.

The notes are part of the config hash, so correcting them re-hashed two runs.
The predictions were untouched and the metrics are byte-identical, verified
before anything was removed:

| experiment | old hash | new hash |
| --- | --- | --- |
| `p3_cw_handtyped_xlmr` | `61f7e7b03355` | `702ab276ae11` |
| `p3_cw_derived_xlmr` | `e264dfc190ac` | `9007de0fde93` |

The two superseded files are deleted rather than kept, because they differ from
their replacements only in a provenance note that was wrong, and `make table`
renders one row per results file — keeping them would put four rows in the
table for two runs. The hashes are recorded here so anything that cited them
can still be traced. `p3_cw_derived_heuristic.yaml` only needed its header
comment fixed, which is not hashed, so that run kept `a7af055a0851`.

**The general lesson is the same one the ablation correction produced**: this
project's numbers have been right and their *labels* have been wrong twice now.
Both times the error was a copy-paste that stayed plausible. The audit that
catches it is reading every published figure back to the file it came from,
including the prose that says what produced it.

### A guardrail that had never once been informative

Noticed while re-scoring the corrected configs. Every results file carries
`git.dirty`, which is supposed to mean *"the committed code does not reproduce
this number"*. It was computed from `git status --porcelain` with no exclusions,
so writing one results file made the tree dirty for the next eval in the same
batch. **All 31 results files in the repo were flagged**, and `docs/results.md`
printed "dirty tree" in the Flags column of every single row.

A flag that fires on 100% of runs carries no information, and worse, it teaches
the reader to ignore the column it lives in — which is the column the sanity
ceiling and the partial-coverage warnings also appear in. Results are *outputs*
and cannot change what a run computes, so `results/` is now excluded. Everything
else still counts, **including untracked source files**, which are exactly the
thing that stops a committed tree from reproducing a number.

`tests/test_provenance.py` pins both halves, since the failure mode of a fix
like this is silently excluding too much. The 31 existing files keep
`dirty: true` and are not rewritten; from this commit the flag means what it
says, so it is only comparable within runs scored after it.

**The first version of the fix was itself wrong, and looked right.** It sliced
`line[3:]` off each `git status --porcelain` line to get the path — correct for
the format, but `_git()` strips its whole stdout, so the *first* line of an
unstaged " M path" arrives with its leading space gone. `M results/x.json`
became `esults/x.json`, matched no exclusion, and reported dirty. Three of five
re-scored runs came out clean and two did not, which is the only reason it was
caught: a fix that fails on every run gets noticed, and one that fails on the
second run onward looks like a fix that worked. Matching the status code as a
leading non-space run survives the strip, and the stripped form is now one of
the test cases.

## Phase 3 gaps — CLOSED 2026-09-24

All four are built. They were, in the order the previous section ranked them:

1. **Zero-shot NLI check-worthiness arm** — built, and it changed the FR-6
   conclusion: 7 of 15 real negatives caught against the trained classifier's 0,
   and the first arm to beat the majority baseline on the hand-typed set.
2. **`tests/test_loader_xclaim.py`** — 15 tests pinning the inclusive-end span
   convention, plus a fabricated-corpus test proving the builder's guard fires.
3. **Measured VRAM in `docs/environment.md`** — §10's ~2.8 GB estimate confirmed
   at 2.588 GiB peak, with the LoRA checkpoint policy written down beside it.
4. **Tests for `src/claims/span_xlmr.py`** — `spans_from_tags`, the adapter
   refusal, the cap and the whole-post fallback.

See the entry above for the numbers and what they changed. **Phase 3 is
complete.** The remaining FR-6 limitation is a data problem with a named owner:
~100 more real no-claim messages, under "Needs a human".

## Next

**Phase 4 — claim matching (Days 5-6).** The fast path: a post that matches an
existing fact-check closely enough skips retrieval entirely. Phase 2 already
built and scored the machinery -- BGE-M3 over 78,077 fact-checks, MRR 0.5244 --
so Phase 4 is mostly wiring it behind `tau_match` and deciding that threshold.

**The floor to beat, per component:**

| component | metric | current | baseline |
| --- | --- | --- | --- |
| Claim span, joint | token F1 | **0.7463** | 0.6851 whole-post |
| Claim matching | MRR / R@10 | **0.5244 / 0.6688** | 0.0002 random |
| Language ID, hand-typed | accuracy | ~0.86 | 0.6400 majority |
| Transliteration, 33 pa pairs | CER | **0.4281** | 0.8518 identity |
| Check-worthiness, hand-typed | macro-F1 | **0.5938** zero-shot NLI | 0.4595 majority |
| AVeriTeC retrieval | R@10 | 0.0947 | 0.0121 random |
| AVeriTeC verdict | macro-F1 | 0.2147 | 0.1516 majority |

**Every component is now above its baseline.** Check-worthiness was the
exception until the zero-shot NLI arm; it clears the majority baseline by
+0.1343 while still rejecting 18 of 85 real claims, so it is the weakest link
rather than a failing one. The constraint is still data — there are 15 real
no-claim messages in the entire project, which is enough to measure an
operating point and not enough to choose one.

**Decision due Day 5:** the demo corpus composition (`SYSTEM_DESIGN.md` §14).
Phase 2's fact-check index makes the retrieve-then-rerank option concrete --
78,077 documents encoded in 12 minutes at 1.11 GiB.

### Open items

- ~~CheckThat! 2025 Task 2~~ **Downloaded 2026-09-24.** No dataset gaps left.
  Still to build: its loader and frozen splits (Phase 3). Use
  `test_gold-*.csv`, not `test-*.csv` — the latter has no labels.
- **An accurate transliterator.** IndicXlit is ruled out in this environment
  (it would install CPU torch over the CUDA build). Options: a character-level
  seq2seq trained on Dakshina's word pairs, or IndicXlit behind a subprocess
  boundary in its own venv. See the Phase 2 entry for why it matters.
- **Knowledge store train split** (63.52 GB) not downloaded. Dev is enough for
  evaluation; only needed if training retrieval on AVeriTeC.
- **A dense index over the full dev knowledge store is not feasible** on this
  GPU: 15.3 M passages, 31.3 GB of fp16 vectors, 14-28 GPU-hours.
  `SYSTEM_DESIGN.md` §7 budgets 3 GB. Use retrieve-then-rerank — BM25 to top-100
  per claim, dense over only those (~0.3 GB, ~15 min). **Settle this before
  Phase 5, not during it.** Phase 2 makes this easier than it looked: the
  fact-check index took 12 minutes and 1.11 GiB for 78,077 documents, so the
  machinery exists and only the scale is the question.
- **`data/interim/index/` is ~1.1 GB** and `tfidf.state.joblib` alone is
  606 MB. Gitignored, but it is there if disk gets tight.

### Needs a human — I cannot do these

- **~100 more real no-claim messages. This is now the top item.** Phase 3
  established that FR-6 cannot be solved with what the project has: X-CLAIM and
  CheckThat! posts are 100% positive, CheckThat!'s subjectivity task covers no
  Indic language, and negatives derived from X-CLAIM's out-of-span remainders
  train a classifier to 0.7222 macro-F1 that then catches **0 of 15** real
  no-claim messages. Greetings, blessings, jokes, pure opinion -- the same
  categories `collection-brief.md` already describes, just more of them. The 15
  already collected are the only reason we know FR-6 is unsolved; ~100 would be
  enough to train on rather than only to fail against.
- **Native-speaker review of `app/static/i18n/{hi,pa}.json`** before any demo.
  Those strings are unverified placeholders, marked as such in the files.
- **Optional: check `hw012`.** Of the seven rows declared `lang=mixed`, six were
  clear; `hw012` has one Punjabi postposition in an otherwise Hindi sentence and
  was assigned `hi`. One row in 100, recorded in `loaders.MIXED_UNCERTAIN`.
- **Optional: set `HF_TOKEN`.** A rate-limit convenience, not a blocker.

### Standing rules that are easy to forget

- Run `make leakage` after **any** data change.
- Never regenerate a committed split. If one looks wrong, stop and ask.
- Every experiment needs a dumb baseline in the same table.
- Before every experiment: what is the current number, what is the dumb
  baseline, and what would make this experiment invalid?

