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

**Seventeen things that are easy to get wrong here:**

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
12. **A symmetric metric encodes a claim about error costs.** FR-6's zero-shot arm
    wins macro-F1 (0.5938 vs 0.4595) and rejects 21% of real claims, which the
    metric prices the same as missing a blessing. The served config runs the
    rules instead. Before shipping the arm that won, ask what each error costs
    the user.
13. **Wire the served config and run two real inputs.** `configs/pipeline/dev.yaml`
    sat on Phase 1 baselines at every stage for three phases while the harness
    scored the real models, because every test built its own config. Two example
    forwards through the real pipeline found an inversion that 3,153 scored rows
    did not. **Phase 5 did it again:** seven forwards found that fact-checks were
    feeding the stance model the rumour itself, and that the served stance model
    ignored its evidence. Rerun them (`docs/project-log.md`, "the demo corpus")
    after any change to the served config.
14. **Every derived label needs a shortcut control.** Derived stance gold labels
    every answer with its claim's verdict, so the claim alone predicts it. Each
    trained stance arm has a claim-only twin trained identically; a model that
    does not beat its twin is not reading evidence. Under the rule aggregator
    the twin even wins the verdict (0.2514) -- that is Phase 6's bar.
15. **A fact-check's claim field is the misinformation.** It is right for
    retrieval and inverted as evidence. `retrieval/corpus.py` reads a
    fact-check as its title; do not "simplify" that back.
16. **A small gap needs an interval before it is a finding.** Phase 6's D4 turned
    on 0.015 macro-F1 over 500 claims, where one claim moves a rare class's F1
    by ~0.03. `paired_bootstrap:` in an eval config gives the 95% CI against a
    prior run; XLM-R's "loss" to its control was a tie.
17. **Faithful is not the same as consistent.** An explanation entailed by some
    retrieved passage can still be the rumour itself: the gate passed a
    word-for-word copy of a refuted claim because one passage asserted it. The
    gate now also rejects, under any verdict but Supported, a sentence that
    entails the claim.

**Where things stand (2026-10-05, end of day; last commit `f4872a7`, 846 tests, lint clean, CI green): the
project is COMPLETE except the demo, the owner's reviews and the relatives' test.** Phases 1-7 are done. The one test
run is scored and written up (`docs/report.md`, `docs/acceptance.md`, `docs/error-analysis.md`, `docs/test-protocol.md`).
**Do not change the served model or any reported number: the test split is spent**, and nothing built after it (live
search, plain card, similar fact-check) ever runs in an evaluation. What was built AFTER the test run, in order
(each has its own entry at the bottom of this log):
1. Romanized free text: lexicon transliteration + a native-script query (report 8a).
2. Live Wikipedia + Google Fact Check search, then a live VERDICT that earned its place: four hand-written probe sets
   rejected it, two pre-registered FEVER measurements decided it (protocol 1 missed its accuracy bar by two claims, protocol 2 on
   350 fresh claims with the owner's real-world labels passed all four gates). Served as: claim translated to English, a page
   judged only if about the claim's subject, DeBERTa-v3-large and BART-large-MNLI must agree (report 8b).
3. A **plain-language card for ordinary readers** (the owner's parents and grandparents are the audience): one verdict word,
   one reason, what to do, sources, Listen, Copy a reply; the full technical card sits in a closed "Details" fold.
4. After the owner tried their own questions: **the offline evidence-path guess is never shown as an answer** (it said
   Refuted to 122 of 125 true claims and to "Paris is the capital of France"). It is now "Be careful with this one: I
   couldn't find a source that checks this exact claim. Most messages like this turn out to be false." (amber) or, for another
   lean, "Hard to say". Verdicts are shown only for a matched published fact-check (fast path) and the live check.
5. A **"similar fact-check" card** ("{publisher} looked at something similar [and rated it False]. This may not be the same
   message."): `ClaimResult.similar_match`, `tau_similar` **0.70** (the owner's post-hoc product decision; the pre-fixed rule gave
   0.86; `docs/similar-factcheck-protocol.md`), offered even when the fact-check's rating cannot be mapped
   (`FactCheckMatcher.similar`, `SimilarMatch`). On 30 typical hoaxes through the real stages: 1 fast-path verdict, 6 similar
   cards, 22 "Be careful", 1 refused by the claim gate.
6. "Check it anyway" for a message the claim gate refuses (`force_claim`, an optional request flag, off by default); the API
   normalizes text to Unicode NFC (two forms of one Punjabi letter gave Refuted vs NEI); `scripts/serve.py` replaces the
   Unix-only `make serve` line (`.venv\Scripts\python.exe scripts\serve.py`).

**WHAT THE OWNER STILL HAS TO DO (nothing else is open):**
1. **Restart the server** (their running one has an OLD backend; the page files are served live from disk, the Python backend
   is not) and hard-refresh (Ctrl+F5). Then `python scripts/demo_check.py` must print OK (not re-run since the last UI changes;
   the chips are unchanged but the Roman-Hindi and long-forward chips are now "Be careful" cards, not verdicts).
2. **Review the new Hindi and Punjabi strings**, all at the bottom of `docs/i18n-review.md` (each section says NOT YET
   REVIEWED and names the `_comment` sentence to remove from `hi.json` and `pa.json` once applied): the honest-card strings (7),
   the similar-fact-check strings (10), the "be careful" and unrated-suggestion strings (4). The 55 plain-card strings and the
   live-verdict strings are already reviewed and applied.
3. **Run the relatives' usability test** with 3-5 people per `docs/usability-test.md` (questions and pass bars fixed before testing;
   task B now expects "Be careful with this one"), send the results sheet, then write `docs/usability-results.md` and update report
   section 6.
4. Rehearse the demo (`UI_UX.md` section 11): fact-checked chip, a similar-fact-check example ("WhatsApp will start charging users from
   next month", "Lemon water cures cancer"), the careful card, a live click ("Hyderabad is the capital of Telangana", "Methyl Phenidate is
   good medicine for ADHD": click once beforehand so the response is cached), the greeting. Read the report end to end once.
5. Optional: `tau_similar` 0.65 (about 13 of 30 hoaxes get a source, ~59% dev precision) is a one-line change in
   `configs/pipeline/dev.yaml`; the deferred live extras (better qualifier judge, more than 30% live coverage) are in memory and
   need a new pre-registered protocol.

**Rules a new session must not re-learn:**
- The test split is locked to the agent: `TRUTHLENS_ALLOW_TEST=1` is refused by the
  permission system. The OWNER runs `bash scripts/run_test_protocol.sh [step]`.
- The Google Fact Check key lives in a git-ignored `.env`
  (`GOOGLE_FACTCHECK_API_KEY`; template `.env.example`). Never print, paste, log or
  commit it; `retrieval/live/http.redact` strips it from cache, logs and traces.
- Decisions here are taken by a rule written BEFORE the run, and a fix is
  validated on FRESH data, never the set that motivated it (live probe sets 1 and 2).
- `rm -rf` is deny-listed. Long shell commands with nested quotes fail: write a
  script file instead. Git-commit messages must not mention the test-split flag.
- **The audience is ordinary people**, not engineers (owner, 2026-10-05): plain words, the reader's language, what to do next, technical detail
  only inside "Details". No language buttons on the page (the owner did not want them); the page language follows the browser or `?lang=`; each
  answer follows its MESSAGE's script (Devanagari or Gurmukhi -> Hindi or Punjabi, Latin letters -> English). The look is the earlier one (15 px
  type, 440 px column); do not enlarge it again.
- **Never show the offline evidence-path verdict as an answer** and never "I am quite sure" on it (see item 4 above). The owner asked for the old
  "Probably false" back; it was declined with the data and the owner accepted the "Be careful" wording. A verdict needs an earned source: fast path or live.
- **The owner runs their own server on port 8000** while testing. Never kill it; never load GPU models in another process while it runs (model loads fail
  with OSError / paging-file errors and results are invalid). For matcher-only checks use `CUDA_VISIBLE_DEVICES=""` on the CPU, or query the owner's
  server over HTTP. A second server for screenshots needs the owner's server stopped.
- **Checking the UI without a browser tool:** Node render checks (`scripts/ui_plain_check.js reports/ui_responses.json`, `ui_render_check.js`,
  `ui_live_check.js`, `ui_evidence_check.js`) plus headless Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe --headless=new --screenshot=...`)
  against a TEMPORARY `app/static/_preview.html` (index.html plus a script that calls `send(...)`); delete it afterwards.
- Decisions are the owner's when they are product choices; record a choice made after seeing the numbers as POST HOC (the `tau_similar` 0.70 entry is
  the model). Pre-registered protocols are never edited after the first run except by dated corrections.

**Working files, all gitignored and on this machine:** AVeriTeC cached passages
`results/preds/p6_passages_{train,dev}.jsonl`; scored passages
`results/preds/p6_scored_*`; every test prediction `results/preds/p7_test_*.jsonl`
and test log `reports/test_run.log`; fold models `data/interim/models/stance_*_fold{0-4}`;
aggregators `data/interim/models/aggregator_*` (served: `aggregator_xlmr_nli_prior`);
explainer `data/interim/models/explainer_indicbart`; passage vectors
`data/interim/dense_cache/`; gold files `data/gold/` (incl. the new
`*_test_*` ones); the live-search response cache `data/interim/live_cache/`;
probe outputs `reports/live_probe_*.{json,md,log}` and error case sheets
`reports/cases/` (they quote dataset text, which never enters git). Committed:
the probe sets `data/probe/live_probe{,_2}.json` (our own wording).

**To get running:** `make setup` then `make test`. The environment is already
built on this machine (Python 3.11 via uv, CUDA torch, models cached on `D:`).

---

## Status at a glance

| | |
| --- | --- |
| **Current phase** | **ALL PHASES COMPLETE (2026-10-05).** Phase 7 done: test run scored, report, acceptance, error analysis. Post-test, all opt-in and never in an evaluation: lexicon transliteration, live search with a pre-registered validated two-model verdict, a plain-language card for ordinary readers, an honest guess card ("Be careful"), a similar-fact-check card, "Check it anyway". Remaining (owner): restart the server, review the new hi/pa strings, the relatives' usability test, demo rehearsal. The test split is spent. Headline test result: served verdict macro-F1 **0.2622** vs claim-only control **0.3085** (paired -0.0463, CI [-0.094, +0.001]) and majority 0.1447. |
| **Clock** | Target **2026-10-12**, no fixed external deadline. Phases 1-7 done 2026-10-02; post-test work 2026-10-04 and 2026-10-05. What is left is the owner's reviews, the usability test, the demo and a read of the report. |
| **Hardware** | i7-14700HX + RTX 4050 laptop GPU, 6 GB VRAM. No Colab. |
| **Branch model** | Trunk-based. Everything commits straight to `main`. |
| **Python** | 3.11.16 via uv, in `.venv`. System Python is 3.13 and is not used. |
| **Served config** | `configs/pipeline/dev.yaml` -- preprocess `hybrid` with the **lexicon** transliterator, claims **`heuristic_span`**, matching `factcheck` (tau_match 0.90), retrieval `hybrid` (RRF@200), free text `corpus` searched with the claim AND its native-script form, stance `xlmr_nli`, aggregate `learned` (aggregator_xlmr_nli_prior), tau_abstain 0.3835, floor off, generation `indicbart` (beam) behind faithfulness `nli`, **manipulation `rules_nli`**, **live_search / live_verdict / live_translate true** (the validated two-model rule; live models offloaded to CPU RAM between uses), **tau_similar 0.70** (the owner's post-hoc choice; rule gave 0.86). `make serve` warms up first. |
| **Tests** | 846 passing, 9 skipped, 2 gpu-deselected (CI has no torch; many ML tests skip there). Clean clone at `023ef3e` passed lint, leakage and 807 tests. |
| **Datasets in hand** | AVeriTeC, X-CLAIM, MultiClaim, handtyped (FR-26), Dakshina, **CheckThat! 2025 T2** |
| **Datasets waiting** | None. Every dataset is downloaded, split, locked and leakage-checked. |
| **GPU stack** | torch `2.9.1+cu128`, CUDA available on the RTX 4050. ~4.9 GiB usable VRAM. |
| **Models trained** | Unchanged since Phase 6; nothing was trained after it. The Dakshina lexicon (not a model) now drives romanization and transliteration. |
| **Numbers so far** | **Test split (the reported numbers, run once):** served verdict macro-F1 **0.2622** (claim-only control **0.3085**, majority 0.1447; paired -0.0463, CI [-0.094, +0.001]) - ECE **0.039** (0.066 at T=1) - at tau 0.3835: 63% answered, accuracy 0.500 (majority 0.567) - retrieval Success@10 0.153 (BM25 0.111) - spans 0.7254 joint / 0.7220 served (whole post 0.6267) - romanized spans 0.7126 vs native 0.7759 on the same posts - matching MRR 0.5355 (BM25 0.3928) - fast path at 0.90: 1.7% answered, precision 0.81 - LID 0.9924 - explanations faithful 0.472 (extractive 0.606) - normalization chrF 0.2666 (baseline 0.2786). Dev numbers: see the Phase 5-6 entries. **Post-test (dev/probe only):** transliteration CER 0.3359; live probe sets 1 and 2 (`docs/live-search-probe.md`). |
| **CI** | Checked with `gh run list` after every push (last green checked: `e43a614`). A sha here goes stale the moment the next commit lands -- check, do not trust. Runs take ~2 min. `gh` is at `C:\Program Files\GitHub CLI\gh.exe`, NOT on this shell's PATH. |

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

## 2026-09-25 — Phase 4: the fast path, and a gate that does not gate

Phase 4 was planned as *"mostly wiring BGE-M3 behind `tau_match` and choosing
that threshold"*. Two measurements taken during planning — both on data and
predictions that already existed, at zero inference cost — said it was not that,
and reshaped the phase before a line was written.

### The retriever ranks well and scores badly

MRR 0.5244 was never wrong. It answers a different question. Every rank metric
is scale-free, and every MultiClaim query is guaranteed to have an answer, so
nothing measured in Phase 2 could say **when to trust the top result**.

Profiled from `results/preds/p2_match_bge_m3.jsonl`:

| | mean | p50 | p90 |
| --- | --- | --- | --- |
| top-1 cosine when top-1 is CORRECT | 0.7239 | 0.7196 | 0.8376 |
| top-1 cosine when top-1 is WRONG | 0.6500 | 0.6321 | 0.7789 |

Heavily overlapping, and the operating curve has no usable point on it:

| τ | coverage | fast-path precision | false accepts |
| --- | --- | --- | --- |
| 0.60 | 77.6% | 51.8% | 64.3% |
| 0.70 | 40.5% | 62.7% | 21.5% |
| 0.80 | 12.4% | 67.3% | 4.8% |
| 0.90 | 1.7% | **81.8%** | 0.3% |

At τ=0.90 the fast path fires on 1.7% of posts and still cites the **wrong**
fact-check 18% of the time. A wrong citation here is this system's worst
failure: it is confident, sourced, and presented as settled.

### The fast path had no verdict to return

`SYSTEM_DESIGN.md` §4 annotates `FactCheckMatch.verdict` as "mapped from the
publisher's rating". Nothing did the mapping. `multiclaim.py` read id, claim,
title and lang, and never touched the `ratings` or `instances` columns — so FR-8,
whose whole sentence ends *"using that fact-check's verdict"*, could not be
satisfied at all.

`src/data/verdicts.py` maps ratings onto the 5-class scheme by **exact match
only**. Substring rules are the obvious shortcut and every one of them is wrong
somewhere that reads fine: `half true` contains `true`, `mostly false` contains
`false`, `partiellement faux` contains `faux`, `salah [misleading content]`
starts with `salah`. An unmapped rating costs a fall-through to the evidence
path, which is where the request was going anyway; a mis-mapped one puts a
confident wrong verdict in front of a user.

Measured, not asserted (`scripts/report_verdict_coverage.py`):

| | pool (78,077) | dev gold (3,943) |
| --- | --- | --- |
| verdict mappable | 79.2% | 81.9% |
| has a URL | 100% | 100% |

Adding nineteen more cognates from the top of the unmapped tail moved dev gold
from 81.7% to **81.9%**. That is the case for stopping: the tail is 13,583
distinct strings whose largest count is 140, so it is flat, not long.

**Two numbers from that table matter more than the coverage figure.** The mapped
distribution is 79.5% `Refuted` and **0.2% `Supported`** — a user whose forward
is TRUE will almost never be told so by the fast path, because fact-checks are
written about false claims. And the pool holds **5 Punjabi fact-checks out of
78,077**, so a Punjabi post cannot match a Punjabi fact-check; it matches
cross-lingually or not at all.

### `task: fast_path`: the harness could not see a decision

`task: retrieval` asks whether the right fact-check is found. The gate asks
whether the score says when to trust it. Same predictions file, same gold file,
different question — so the new task reuses both unchanged and costs no new data
and no new inference.

Design decisions worth keeping:

- **Negatives by withholding the answer, derived in the scorer.** For each query
  the best-scoring returned candidate that is not gold is, by construction,
  wrong. For a cosine scorer this is exact rather than simulated: a pair's score
  does not depend on what else is indexed. It is only approximate for BM25,
  whose IDF is corpus-dependent. And `false_accept_rate` is an **upper bound**
  either way, because MultiClaim's annotation is incomplete and a non-gold
  fact-check may genuinely match. Not a config flag: the one number that makes
  the fast path look bad must not be the optional one.
- **The headline is AUCC**, the area under the coverage-precision curve, because
  every other candidate is a knob. Precision is monotone in τ (81.8% at 1.7%
  coverage is not an achievement), and yield is maximised at τ = −∞. **The τ
  table is the result**; the headline exists because a results table needs one
  column.
- **The baseline is `always_match`** — the same ranking with the gate removed,
  so its AUCC is Success@1 and the delta against it is the gate-worthy signal in
  the score and nothing else.

### The lexical floor was understated

`src/retrieval/CLAUDE.md` says BM25 is the real baseline, and none existed over
the fact-check pool; Phase 2's ladder used TF-IDF (MRR 0.2311) as a stand-in.

| | MRR | R@10 | AUCC | vs `always_match` |
| --- | --- | --- | --- | --- |
| TF-IDF (Phase 2) | 0.2311 | 0.3045 | — | — |
| LaBSE (Phase 2) | 0.3216 | 0.4170 | — | — |
| **BM25** | **0.3826** | 0.4570 | 0.3420 | +0.0173 |
| **BGE-M3** | **0.5244** | 0.6688 | **0.5842** | **+0.1557** |

So the real lexical floor is well above what Phase 2 reported. BGE-M3 still wins
on **every single cell**, including romanized Hindi, where I expected BM25 to
win and said so in the plan.

Two things the average hides. **BM25's gate is nearly worthless** — +0.0173 AUCC
against BGE-M3's +0.1557 — and the reason is structural: a BM25 score is a sum
over query terms, so a long post scores high for being long, while a cosine is
length-normalised. Top-1 BM25 scores here run 0.00 to 3376.42. A single global τ
cannot mean the same thing for two queries of different lengths.

And **BM25 scores 0.0000 MRR on Punjabi**, both cells (n=7, n=2). With 5 Punjabi
fact-checks in the pool there is no lexical overlap to find, so BGE-M3's 0.4333
there is entirely cross-lingual transfer. The same pattern Phase 2 found for
TF-IDF replicates: BM25's *romanized* Hindi (0.2251) beats its *native* Hindi
(0.1936), because Latin characters are shared with a largely English corpus and
Devanagari shares none.

### Engineering that was worth the detour

`rank_bm25` scores a query by looping in Python over all 78,077 documents once
per query term. A 3,153-row split took over an hour, and its ~1.5 GB of
per-document dicts were paged out on this 16 GB machine, after which it crawled.

Okapi BM25 ignores query-term weighting, so every (document, term) weight is
query-independent and precomputes into one sparse matrix; a query is then
`W @ v`. **17.4 ms/query against 1070 ms, and 14 MB of CSR against ~1.5 GB.**
The arithmetic is `BM25Okapi`'s exactly, including its negative-IDF floor, and
it is tested against `rank_bm25` as an independent oracle rather than against
itself.

My first estimate of the cost was wrong, and the reason is worth keeping: I
benchmarked on a 12-token query when MultiClaim dev posts average 59.8 tokens
with a p99 of 542, so the real cost was 5× the projection. **Benchmark on real
inputs.**

### Three bugs, two of them latent for three phases

- **`_from_factcheck` fed a raw retrieval score into a validated field.**
  `ClaimResult.confidence` is `Field(ge=0.0, le=1.0)` and a cosine can be
  negative while a BM25 score is ~20, so the fast path raised a
  `ValidationError` at request time. It survived three phases because
  `NoMatcher` never returned a match. Now clamped, with the trace recording both
  the clamp and the fact that a fast-path confidence is uncalibrated.
- **`FactCheckMatch.lang` is `en|hi|pa|other`** and MultiClaim covers 39
  languages — 42,899 of the pool are outside our three.
- **`always_match` assigned a literal score of 1.0.** Above every cosine, far
  below a BM25 score. On the BM25 arm (τ from 20 to 400) "the gate removed"
  accepted *nothing* and reported coverage 0.0000 where it must report 1.0. It
  now takes the run's own maximum. **The BM25 row is what caught it** — the
  same argument as Phase 3's: a second arm on a different scale is what makes a
  silent assumption visible.

### Smaller things

`{"n", "n_skipped_no_relevant"}` was hard-coded in three places to decide what
counts as a metric, and `n_accepted` would have tripped the sanity ceiling on
every fast-path run. One `is_metric()` rule now, which also fixes a latent bug:
`isinstance(True, int)` is `True`, so a boolean was being read as a score.

`HEADLINE` existed twice, in `evaluate.py` and `report.py`, with nothing
comparing them — a task added to one and missed in the other rendered every row
of its table against `mrr`, with a wrong label and a blank score. `report.py`
now holds the only copy, and an unregistered task renders blank rather than
borrowing another task's metric.

A no-reranker control arm was written and then deleted as a duplicate. The
reranker arms rerank the top-10 that `p4_fastpath_bge_m3`'s retrieval returns,
through the same `DenseRetriever` over the same index — and the one thing that
could have differed, the language layer, does not: measured across every cell,
`passthrough` and `hybrid` produce byte-identical query text for 306/306 rows,
because the language layer sets lang, script and a transliteration without
rewriting `normalized`. Twelve GPU-minutes and a duplicate table row saved by
checking instead of assuming.

### The ablation: four gates, and the raw cosine wins

All four score the same 3,153 MultiClaim dev queries against the same
78,077-fact-check pool. `always_match` is the same ranking with the gate removed,
so its AUCC is that arm's Success@1 and the delta is the gate-worthy signal in
the score alone.

| gate | Success@1 | AUCC | vs gate-removed | prec @ ~40% coverage |
| --- | --- | --- | --- | --- |
| BM25 (lexical) | 0.3283 | 0.3420 | +0.0173 | 35.8% |
| zero-shot NLI reranker | **0.1062** | 0.1153 | +0.0086 | 10.8% |
| trained XLM-R reranker | 0.4342 | 0.5508 | +0.1154 | 59.3% |
| **BGE-M3 cosine, no reranker** | 0.4326 | **0.5842** | **+0.1557** | **62.7%** |

**The raw cosine is the best gate of the four.** That is not what the phase set
out to find, and the two reranker results are the useful part.

**Zero-shot NLI actively destroys the ranking**: Success@1 falls from 0.4326 to
**0.1062**. The limitation written into the docstring before the run turned out
to be the whole story — NLI asks whether one text entails another, and a
fact-check that *debunks* a claim contradicts the post making it. Entailment is
the wrong relation for "these are about the same claim". Phase 3's zero-shot arm
won its ablation; this one loses by a mile. **Trained-versus-zero-shot is not a
rule, it is a question, and it has to be asked per task.**

### The trained reranker learned to score fact-checks instead of pairs

It looked like it was working. Mean score separation between a correct and a
wrong top-1 **doubled**: +0.1465 against the cosine's +0.0739. But AUCC came out
*lower* (0.5508 vs 0.5842), and the τ table says why — at τ=0.90 its precision
**collapses to 9.8%** on 41 rows. Its most confident answers are its most wrong.

Three measurements, each ruling something out:

1. **Not annotation incompleteness.** The obvious excuse is that MultiClaim's
   gold is incomplete and those confident "errors" are really good matches marked
   wrong. They are not: mean token-Jaccard between the wrong high-confidence
   pick and the post's actual gold is **0.049**, and **0 of 37** are
   near-duplicates of it. They are about unrelated subjects.
2. **The score barely depends on the post.** Across the 622 fact-checks that
   appear as a candidate for five or more dev posts, the overall score SD is
   0.224 while the mean *within-candidate* SD is **0.057** — about three
   quarters of the variation is explained by which fact-check it is, not by the
   pair. Per-candidate mean scores span 0.001 to 0.704.
3. **It is memorising which fact-checks are ever a gold answer.** Candidates that
   were **never** a positive in training average P(relevant) **0.0500**; those
   seen as a positive 2–4 times average **0.1596** — a 3.2× difference, Pearson
   r = +0.250 against the log positive count.

So the model found a shortcut that the mining handed it. Positives are the
annotated golds and negatives are top-10 non-golds, which means *"is this
fact-check ever somebody's answer"* predicts the label without reading the post
at all. A cross-encoder that never has to look at the post cannot order
candidates within a query, which is exactly what a gate needs.

**This is a training-data construction bug, not a model failure**, and the plan
predicted the shape of it: *"If it does not beat the zero-shot control, suspect
the hard-negative mining before the model."* It did beat the zero-shot control,
and the mining was still the problem.

The fix is to destroy the shortcut: every candidate has to appear on both sides
of the label, so a fact-check's identity carries no information about relevance.
Sampling some negatives from *other posts' gold* does that.

Resampling was the obvious fix and it was measured before being paid for, which
is the only reason it was not. Drawing extra negatives from **other posts' gold**,
frequency-weighted so a candidate's positive rate stays constant, moves the
correlation from **+0.803 to +0.768** and shrinks the spread across ever-gold
candidates from sd 0.1645 to 0.1035. It cannot do better: a candidate that is
never any train post's gold has a positive rate of exactly **0.0000**, and no
sampling scheme changes that. Identity still answers *"could this ever be a
positive"*.

So the shortcut is in the objective. The fix is to train **within a query** -- a
listwise softmax over each post's candidate list with its gold as the target -- so
the model is scored on ordering candidates for one post, where a global
per-candidate prior has much less to offer. That is a Phase 6 change, not a
Phase 4 one; `--gold-negatives` stays in the miner at default 0, with its number
beside it, because a rejected experiment with a measurement is worth more than a
deleted one. **Retraining was not attempted**, on the grounds that a two-and-
three-quarter-hour run against a fix already measured to move r by 0.035 is not
a good trade.

### The served pipeline was still running Phase 1 at every stage

Found before implementation started and worth its own line: `configs/pipeline/dev.yaml`
had `preprocess: passthrough` and `claims: passthrough`. Everything Phases 2 and
3 built was measured by the harness and **not served**, and because
`PassthroughClaims.check_worthy` returns True for any non-empty string,
`NotAClaim` -- the first card in the demo script and the answer to PRD scenario
S4 -- was unreachable in the API. Nothing caught it because every test built its
own `PipelineConfig`; `tests/test_orchestrator.py` now loads the real file.

### Wiring it found something no metric had

With the config pointing at the arms that won their metrics, the pipeline was run
on two forwards. It **inverted both**: `NotAClaim` for *"Sarkar ne announce kiya
hai ki har student ko 6000 rupaye milenge"*, and check-worthy for a Punjabi
blessing.

The cause is the FR-6 arm selection, and the numbers were on record the whole
time:

| claims impl | macro-F1 | real claims rejected | no-claims caught |
| --- | --- | --- | --- |
| nli (zero-shot) | **0.5938** | **18/85 = 21.2%** | 7/15 |
| xlmr (trained) | 0.4536 | 2/85 = 2.4% | 0/15 |
| heuristic (rules) | 0.4595 | 0/85 = 0.0% | 0/15 |

**macro-F1 picks `nli`; the product does not.** The two errors are not symmetric
and macro-F1 treats them as if they were. A false `NotAClaim` fails the user
completely -- they forwarded a rumour and the system said there is nothing to
check, with no verification and no recourse. A false check-worthy costs an NEI
answer on a blessing: silly, harmless. One in five real claims is too high a
price for catching seven blessings.

So the served config runs `claims: heuristic` while the **reported** FR-6 result
stays `nli`, which is still the best arm on the metric. Both are recorded, and
the served choice is revisitable the moment there are enough real no-claim
messages to pick an operating point that does not cost claim recall.

The transferable part: **a symmetric metric silently encodes a claim about
relative error costs.** Nothing in the harness is wrong here — macro-F1 measured
exactly what it says. Two example forwards through the real pipeline showed what
3,153 scored rows could not.

### Semantic near-duplicate leakage, which SimHash cannot see

`data/CLAUDE.md` assigned this to Phase 4: *"Embedding-based duplicate detection
belongs in Phase 4 alongside the claim-matching retriever. Until then,
`make leakage` passing means no duplicates, not no overlap."* Built as
`scripts/check_semantic_leakage.py`, and the cut is **calibrated against two
measured distributions per dataset** rather than assumed, the way the SimHash
thresholds were in Phase 0:

| dataset | known near-dups (SimHash ≤ 4), p5 | random unrelated pairs, p95 |
| --- | --- | --- |
| x_claim | 0.9703 | 0.4642 |
| multiclaim | 0.9245 | 0.4568 |
| checkthat25_t2 | 0.9420 | 0.4683 |
| averitec | 0.8337 | 0.4470 |

Two cleanly separated distributions on every dataset, so a cut of **0.90** sits
inside the near-duplicate lower tail and roughly twice above the unrelated
ceiling. It therefore errs toward **missing** near-duplicates rather than
inventing them — every count below is a lower bound, and AVeriTeC's p5 of 0.8337
says the undercount is largest there.

What it finds, counting only rows the SimHash check cannot see (Hamming > 8, its
fail threshold):

| dataset | dev flagged | dev NEW | test flagged | test NEW |
| --- | --- | --- | --- | --- |
| averitec | 6/500 (1.2%) | 5 | 31/307 (10.1%) | 27 |
| checkthat25_t2 | 110/1271 (8.7%) | 91 | 164/1485 (11.0%) | 130 |
| **multiclaim** | **373/3153 (11.8%)** | **287** | 390/3156 (12.4%) | 317 |
| x_claim | 19/600 (3.2%) | 16 | 19/571 (3.3%) | 14 |
| xclaim_cw | 36/963 (3.7%) | 30 | 37/970 (3.8%) | 28 |

**945 eval rows across the project** are semantic near-duplicates of a training
row that `make leakage` passes.

**Which results this actually touches is narrower than the table suggests**, and
the distinction is whether anything was trained on that dataset's train split:

- **Nothing.** AVeriTeC retrieval and verdict (BM25 and off-the-shelf NLI),
  CheckThat normalization (extractive), and MultiClaim claim matching (BGE-M3 is
  off-the-shelf and the index is the fact-check pool, not the posts). A model
  that never saw train cannot have memorised it.
- **The span model**, on x_claim: token F1 0.7463 is measured on a dev set where
  2.7% of rows are invisible near-copies of training rows.
- **The check-worthiness classifier**, on xclaim_cw: 3.1% of dev.
- **The claim-matching reranker**, on multiclaim: 9.1% of dev. It inflates the
  arm that lost anyway, so that conclusion is if anything safer than reported.

**Recommendation: state it, do not rebuild.** Two reasons beyond `CLAUDE.md`'s
first non-negotiable. The contamination is small on exactly the splits that feed
trained models (2.7% and 3.1%), and rebuilding would invalidate every Phase 1-4
number for a correction of that size. More interestingly, on MultiClaim the
near-duplicates **are the phenomenon**: the same rumour is forwarded thousands of
times, which is precisely why a fast path is worth building. Removing
near-duplicate posts across splits would make the claim-matching benchmark less
like deployment, not more — in deployment, nearly every input is a near-duplicate
of something already fact-checked.

### Where FR-8 actually stands

`tau_match: 0.90`, chosen on dev, recorded in the served config and reported by
`GET /version`. At that threshold the fast path fires on **1.7% of posts (n=55)**
and is **still wrong about one time in five**. Lower thresholds buy coverage at a
price the product cannot pay: 40.5% coverage costs 37.3% wrong citations.

So FR-8 is **measured, not demo-ready**, and the reason is not the threshold. It
is that the best available signal separates a right match from a wrong one too
weakly, and the two obvious ways to strengthen it have both been tried and
measured. The honest options from here, in order of expected value:

1. **A within-query reranker objective** (above). The shortcut diagnosis makes
   this a specific change with a specific prediction, not a hope.
2. **A cross-encoder somebody else trained** -- `BAAI/bge-reranker-v2-m3` is
   purpose-built for exactly this and was declined during planning on download
   risk. That decision looks worse now than it did.
3. **Present the fast path as a related fact-check rather than a verdict.** At
   68% precision the top match is genuinely useful as *"here is a fact-check that
   may be about this"* and dishonest as *"already checked, verdict Refuted"*. This
   is a `UI_UX.md` question, and it is the cheapest of the three.

## 2026-10-01 — Phase 5: evidence retrieval and stance

FR-9 (hybrid retrieval) and FR-10 (stance), both P0. Phase 1 had left the
verdict stuck behind retrieval -- Success@10 0.158, so the stance model read
irrelevant text on most claims -- and this phase was where it was meant to move.
Five measurements were taken before anything was designed, and two of them
changed the plan.

### A bug that would have corrupted the final number

`claim_index_from_uid` kept only the integer from `averitec:train.json:133`, and
the batch runner looked it up in `KnowledgeStore(cfg.split)`, which defaults to
`dev`. The local AVeriTeC **test** split is 307 claims held out of the public
train.json, so a test claim with index below 500 silently read an **unrelated
dev claim's evidence pool**, and one above 500 got NEI from a missing file. No
error either way; it had not fired only because nothing had yet run on test.

The same hard-coded dev archive sat in `kb.py` and `build_kb_cache.py`, so
`--split train` would have written the dev store into the train cache.

Fixed before any Phase 5 number: the store now comes from the row's source_id,
`KB_ZIPS` is the one map of which archives form which split, and the cache
builder refuses an archive the download manifest does not vouch for, builds into
`.partial/`, and verifies the claim-to-file mapping two ways before publishing.
Measured on the real archives rather than inferred from file names: all three
train zips use global claim indices, own-claim QA agreement 100% against 3.8% for
the neighbour, and a dev rebuild is byte-identical to the Phase 1 cache.

The train store took 8 hours to build, mostly from contention, and one number
from it matters for Phase 6: **3,504 of 6,458 train gold documents (54%) have no
text** -- worse than dev's 40%.

### Ceilings, measured before building

- **A fifth of dev can never be retrieved correctly.** 443 of 1,096 dev gold
  documents have no text, and for 114 of 500 claims every gold document is empty.
  Success@10 cannot exceed **0.772** for any text retriever.
- **BM25 finds the gold, just too deep:** Success@10 / 50 / 100 / 200 / 500 =
  0.158 / 0.350 / 0.474 / 0.584 / 0.700 (`p5_retrieval_bm25_depth`, through the
  harness). Success@N is the ceiling on a reranker over BM25's top N.

### Stance has no gold, so it was derived -- and the derivation is a trap

AVeriTeC annotates a verdict per claim and QA evidence per claim, but no stance
per piece of evidence. `averitec_stance` is one row per QA answer, labelled with
its claim's verdict: 6,616 train / 1,260 dev / 789 test, split membership
**inherited** from the frozen AVeriTeC splits so no test claim can train.

The gold is noisy by construction, and dev row 0 shows it: *"Where was the claim
first published? It was first published on Sccopertino"* is labelled Refutes,
because its claim is refuted.

Worse, it has a built-in shortcut: every answer of a claim shares one label, so
within a claim the evidence cannot change the label, and across claims the claim
alone predicts it. So every stance model got a **claim-only twin**, trained
identically on the claim alone.

| arm | all 1,260 rows | answered 1,222 | vs claim-only twin |
| --- | --- | --- | --- |
| majority_class | 0.2663 | | |
| zero-shot NLI | 0.3339 | 0.3183 | -0.1036 (TF-IDF twin) |
| TF-IDF, claim only | 0.4177 | 0.4220 | (twin) |
| TF-IDF | 0.5554 | 0.4183 | **-0.0036** |
| BiLSTM | 0.5006 | 0.4012 | -0.0208 (TF-IDF twin) |
| XLM-R, claim only | 0.4032 | 0.4098 | (twin) |
| **XLM-R** | **0.5945** | **0.4582** | **+0.0484** |

Three findings:

1. **TF-IDF's apparent evidence lift was one string.** On all rows it beat its
   twin by +0.1377. The 38 Unanswerable rows are all the literal *"No answer
   could be found."*, which the derivation relabels Neutral; TF-IDF gets 38/38,
   the twin 3/38. On the 1,222 rows where an answer was found, TF-IDF reads
   nothing the claim did not already say. My own relabelling made that string
   trivially learnable -- the third shortcut in two phases.
2. **Only the cross-encoder reads usable evidence.** XLM-R beats its own twin by
   +0.0484 on answered rows; neither the bag of words nor the BiLSTM gains
   anything there. That is the expected ordering: the only usable evidence signal
   under these labels is a relation that transfers across claims ("Did X say Y?
   No, he never said it" refutes the claim), which a model reading both texts
   together can represent and the others cannot.
3. **Zero-shot NLI scoring lowest here is not evidence that it is the worst
   stance model.** It predicts Neutral for 516 of 838 gold-Refutes rows, and most
   of those are background answers that genuinely neither entail nor contradict
   the claim. When it commits to Refutes it is 75% precise. This is the Phase 3
   trap again -- a constructed set ranking models by something other than the
   task -- which is why **verdict macro-F1 on AVeriTeC dev, whose gold is clean,
   picks the stance model**, not this table.

The answered-only figures go through the harness via `allow_partial`, each full
model's baseline set to its claim-only twin's run on the same rows, so the delta
is exactly the evidence lift. The frozen split was not regenerated to drop the
38 rows; it was committed minutes before the string was found, and `CLAUDE.md`
says not to.

### Hybrid retrieval: every arm beats BM25, and depth is not the limit

BM25 per claim -> top N -> BGE-M3 passage rerank (~1,000-character passages,
document scored by its best passage, MaxP) -> fused. The best passage is what
stance reads, replacing the lexical paragraph picker. Passage vectors are cached
by document, so one 45-minute build served every arm below.

| arm | Success@10 | MRR | ceiling at that depth |
| --- | --- | --- | --- |
| BM25 (Phase 1) | 0.158 | 0.0656 | |
| RRF, depth 100 | 0.212 | 0.0863 | 0.474 |
| **RRF, depth 200** | **0.214** | 0.0888 | 0.584 |
| dense only, depth 100 | 0.204 | 0.0906 | 0.474 |
| dense only, depth 200 | 0.206 | **0.0924** | 0.584 |
| weighted, depth 200 | 0.172 | 0.0715 | 0.584 |

I predicted 0.35-0.45. The reranker recovered about 13% of the headroom, and the
reason was measured, not assumed: 292 of 500 claims have a non-empty gold in
BM25's top 200, and BGE-M3 lifts the best gold to a **median rank of 21** of
those 200 -- top 50 for 75% of claims, top 10 for 35%. The gold's best passage
scores a median cosine of 0.653 against 0.555 for the median distractor: a gap of
0.09, because **AVeriTeC's pools are web-search results for that claim and the
distractors are on-topic too.** A bi-encoder separates on-topic from off-topic
well and gold from on-topic poorly. That is the case for a cross-encoder
reranker.

Depth 100 -> 200 adds 0.002, so extending the cache to depth 500 (~2 more
hours) was cut on that measurement. Weighted fusion is worst because cosines
here sit in a narrow band while min-max BM25 spans 0-1, so BM25 dominates the
mix; RRF is rank-based and immune.

### The verdict: better retrieval exposed the aggregator, and the claim alone won

Retrieval fixed at RRF depth 200, the Phase 1 rule aggregator unchanged, only
the stance model varied. AVeriTeC dev, clean gold:

| stance | verdict macro-F1 | Conflicting predicted (gold 38) |
| --- | --- | --- |
| **XLM-R, claim only** | **0.2514** | **0** |
| TF-IDF | 0.2323 | 49 |
| *Phase 1: BM25 + NLI* | *0.2147* | *141* |
| XLM-R | 0.2082 | 214 |
| BiLSTM | 0.2065 | 141 |
| zero-shot NLI | 0.1989 | 246 |
| majority_class | 0.1516 | |

**Better retrieval made the NLI verdict worse** -- 0.2147 to 0.1989 while
Success@10 rose. More on-topic passages give the stance model confident signals
in both directions, and the rule aggregator (max P(Supports) and max P(Refutes)
over k passages, Conflicting if both clear 0.5) turns that into Conflicting:
141 predictions in Phase 1, 246 now. Refuted F1 falls 0.547 -> 0.412 as refuted
claims get called Conflicting. Phase 1 flagged this aggregator as a Phase 6
problem; better retrieval made it the bottleneck.

**The control that never reads evidence produces the best verdict**, and the
ranking is almost exactly the inverse of how often each arm triggers
Conflicting. The claim-only model scores every passage of a claim identically,
and one distribution cannot put both Supports and Refutes at 0.5 -- so it
*cannot* trigger the rule. **Under this aggregator the verdict rewards a stance
model for not reading evidence.** This is a version of the claim-only bias known
from fact-verification datasets, here amplified by the aggregator.

Three consequences:

- **Plan decision D4 does not hold yet.** "The verdict picks the stance model"
  assumed an aggregator that was neutral between stance models. This one is not,
  so the stance choice moves to Phase 6 and is made against the learned
  aggregator. The served pipeline takes XLM-R provisionally: the only arm shown
  to read evidence, and serving a model that ignores evidence would contradict an
  explanation that cites it.
- **Phase 6's bar is 0.2514, not 0.2147.** Any claim that evidence helps the
  verdict has to beat the claim-only control.
- **The relevance floor (FR-12) is built, tested, and off.** Choosing its value
  now would tune a threshold against a broken aggregator -- the same reason
  Phase 1 gave for not tuning the aggregator before retrieval.

### Smaller things worth keeping

- **Two more bugs the degradation path or a counter caught.** A document with no
  text got a (0, 0) vector array whose concatenation raised inside the
  retriever's degradation handler, so every run silently fell back to BM25 and
  cached nothing -- a test counting encodes saw it, and the batch runner now
  REFUSES a run in which any claim degraded. And a URL shared by two claims'
  pools was cached only under the first, so every later run re-encoded it.
- **The train knowledge-store build and the dense build together dropped the
  dense build from 56 to 3 passages/s** -- free RAM 1.06 GB, the 63 GB zip stream
  evicting everything. Alone it ran at 121/s. Measured claim by claim, the
  6.5 GiB private footprint was not a leak (torch, CUDA and the model, committed
  once); the one-job-at-a-time rule is about memory and disk, not just VRAM.
- **pandas is not in CI's core lock**; the TF-IDF pipeline used it and three
  tests failed on the runner. Rewritten without it; both arms reproduce their
  config hashes exactly.
- **All 19 split files reproduce byte-for-byte**, including the three new ones,
  and CI's reproducibility job rebuilt `averitec_stance` from public data.

### The demo corpus, and two inversions only real forwards could show

Decision D7, built: Hindi and Punjabi Wikipedia **lead sections** plus the 78,077
fact-checks as one global index (`retrieval/corpus.py`), so a free-text forward
-- every real forward -- gets an evidence path. Until now each one that missed
the fast path answered "no evidence corpus is available".

| part | documents | notes |
| --- | --- | --- |
| hi leads | 154,259 | of 175,284 articles; 21,025 had no usable lead |
| pa leads | 57,410 | of 60,023 articles |
| fact-checks | 78,077 | Phase 4 vectors reused, not re-encoded |

Dumps pinned to the 2026-09-01 snapshot (hi 240 MB, pa 96 MB) with sha256 in
`DOWNLOADS.json`; leads extracted in 2.2 minutes with a stdlib regex stripper (no
wikitext library is installed), 211,669 encoded at ~140 docs/s, 0.59 GB of
vectors. Search is global BM25 top 100 UNION global BGE-M3 top 100, fused by
RRF; the dense side proposes its own candidates because there is no pool to
rerank. Every result carries a cosine, so the relevance floor can read one. The
AVeriTeC knowledge store is not in it (decided in planning, now recorded in
SYSTEM_DESIGN §14). ~1 s per forward warm; the first takes ~40 s to load models.

**The corpus has no gold, so it has no metric.** It was checked the way Phase 4's
wiring was: real forwards through `configs/pipeline/dev.yaml`. Both of the
following were invisible to every number in this entry.

**1. Fact-checks were handing the stance model the rumour.** A fact-check is
indexed as "claim + title", which is right for retrieval -- a forward repeats
the claim. As evidence it is inverted: the claim field IS the misinformation,
stated as fact. "नींबू पानी पीने से कैंसर ठीक हो जाता है" (lemon water cures
cancer) came back **Supported, 0.815**, because one passage began "Cancer ... can
be cured using hot lemon water" and NLI correctly found that it entailed the
claim. A fact-check's passage is now its **title** -- the fact-checker's own
conclusion -- and never its claim; the same forward now answers Refuted.

**2. XLM-R stance does not read the evidence on this corpus.** Same passages,
three stance models, seven forwards (four true, three false):

| | xlmr | xlmr claim-only | nli |
| --- | --- | --- | --- |
| passages labelled as the claim-only twin labels them | 5 of 7 forwards identical | -- | -- |
| verdicts | Refuted/Conflicting on **all 7** | | 3 right, 4 wrong |
| "दिल्ली भारत की राजधानी है" (true) | **Refuted** | | Supported, 10/10 passages |

XLM-R gets the three false claims "right" and every true claim wrong: that is
its AVeriTeC prior (68% Refutes), not evidence. The +0.0484 it showed over its
twin on derived dev does not transfer to Wikipedia leads and fact-check titles.
NLI's four errors are the aggregator's: one Refutes among nine Supports makes
Lahore-is-the-capital Conflicting, and two fact-check titles that say "No ..."
about a different Gujarat story make a true Modi claim Refuted. **The served
stance is now `nli`**, reversing the provisional `xlmr` above on its own stated
premise -- serve the model that reads the evidence its explanation cites. Seven
forwards are not a metric and do not settle D4; Phase 6 still does.

**What this hands Phase 6.** Max-over-k lets one passage of ten decide the
verdict, and that is now the visible failure on the demo as well as on dev. The
learned aggregator should see the whole distribution, and fact-check titles that
debunk a *different* claim about the same entity are the hard negatives for it.

## Phase 5 — COMPLETE 2026-10-01

FR-9 and FR-10 are built and measured; the demo corpus is built and wired.
Served config: retrieval `hybrid` (RRF, depth 200), free text `corpus`, stance
`nli` (provisional), relevance floor off. Also fixed: two stance refusal tests
imported torch, which CI's core lock lacks -- CI was red for two pushes
(`cb9b15e`, `838e7b9`) before `6dce339`. Suite: 548 passing.

## 2026-10-02 — Phase 6: aggregation, calibration, abstention, grounded generation

FR-11 (aggregation), FR-12's floor value, FR-13 (calibration), FR-14
(abstention), FR-15/16/18 (generation behind an NLI gate), and plan decision D4
-- which stance model the verdict uses. Phase 5 handed over one problem: the rule
aggregator (max P(Supports) / max P(Refutes) over k passages) rewarded stance
models for ignoring evidence, so the claim-only control won the verdict (0.2514)
and that became this phase's bar.

### Decided with the project owner before building

1. **Cross-fit the stance models** for the aggregator's training data. XLM-R and
   the BiLSTM were trained on every QA answer of every train claim, labelled with
   that claim's verdict; scored on those claims, they would hand the aggregator
   outputs far more confidently right than on any unseen claim. Five claim-level
   folds (a seeded hash of the claim id, so no claim straddles two), ~35 min of
   GPU in total -- XLM-R trains in 2.6 min per fold.
2. **English explanations** from IndicBART, behind the NLI gate. AVeriTeC's ~3,000
   justifications are the only explanation gold and they are English; hi/pa input
   gets an English explanation (cut-list item 3). No regression: every
   explanation was English before.

### Infrastructure first

- **The harness now scores calibration** (opt-in `calibration:`): ECE,
  reliability bins, the coverage curve with macro-F1 at each point, and the
  abstention operating point -- the lowest tau whose coverage is <= 60%, a
  criterion fixed in the plan before any number was seen. Opt-in and outside
  DEFAULTS, so no existing config hash moved.
- **`task: faithfulness` is implemented** in `src/eval/`: an explanation is
  faithful iff EVERY sentence is entailed (mDeBERTa XNLI, P >= 0.5) by some
  passage it was shown. The pipeline's gate calls the same function, so "passed
  the gate" and "graded faithful" cannot mean different things.
- **Paired bootstrap** (opt-in `paired_bootstrap:`): a 95% CI on the macro-F1
  delta against a prior run, resampling the same claims for both systems. Added
  mid-phase when D4 turned on a 0.015 gap: with 35-38 claims in the rare classes,
  one claim moves a class F1 by ~0.03.
- **Retrieve once, score many times.** `--stage passages` caches each claim's
  top-20 hybrid passages; every stance arm, fold and k reads that file. The
  offline features and the live orchestrator agree on 500/500 dev verdicts for
  XLM-R, its control and the BiLSTM (confidence within 1e-6); NLI 496/500
  (within 0.045), fp16 mDeBERTa at 512 tokens being sensitive to batch padding.

### D4: no stance model that reads evidence beats the claim-only control

Learned aggregator: multinomial LR over 19 features of the whole top-10 stance
distribution in rank order, balanced class weights, trained on cross-fitted
AVeriTeC train, temperature fitted on dev. AVeriTeC dev, macro-F1, paired
bootstrap over the same 500 claims:

| stance | macro-F1 | accuracy | vs learned control [95% CI] |
| --- | --- | --- | --- |
| **XLM-R claim-only (control)** | **0.2949** | 0.470 | (+0.0435 vs the rule, [+0.007, +0.078]) |
| XLM-R | 0.2802 | 0.490 | -0.015 [-0.062, +0.030] -- a tie |
| BiLSTM | 0.2340 | 0.388 | -0.061 [-0.100, -0.018] |
| zero-shot NLI | 0.2135 | 0.320 | -0.081 [-0.124, -0.039] |
| *Phase 5 bar: control, rule* | *0.2514* | *0.582* | |

Two findings:

1. **The learned aggregator is a real gain**, and its CI excludes zero. It does
   what it was built for: Conflicting F1 goes from 0.000 under the rule to ~0.20
   for both XLM-R arms (38 dev claims).
2. **Reading the evidence adds nothing measurable on AVeriTeC.** XLM-R ties its
   claim-only twin; NLI and the BiLSTM are significantly worse. Phase 5's
   derived-stance result (+0.0484 for XLM-R over its twin) does not survive to
   the verdict. The cross-fitting matters to this conclusion: without it the
   evidence arms' train features would have been inflated, and the comparison
   would have favoured them for the wrong reason.

**The served stance stays `nli`**, by the approved plan's rule (no arm beats the
control -> report it, keep the served stance). That keeps the arm with the
weakest AVeriTeC number (accuracy 0.32 against a 0.61 majority class) and the
only one seen reading evidence on real forwards (Phase 5). That is a product
trade-off, not a measurement, and it is put to the project owner below.

### Floor, temperature, abstention -- all on dev

- **Relevance floor: off.** On the served arm, floors 0.45 and 0.50 abstain on
  zero dev claims; 0.55 abstains on 3 (-0.0028, [-0.0062, 0.0000]); 0.60 on 9
  (-0.0065, [-0.0118, -0.0021]). It cannot be tuned on AVeriTeC at all: pools are
  retrieved FOR each claim (Phase 5: median distractor cosine 0.555). On the demo
  corpus, where it would matter, there is no gold.
- **Temperature (FR-13):** ECE 0.0590 at T=1 -> **0.0384** at the fitted
  T=1.389; macro-F1 unchanged, as temperature cannot move an argmax. Fitted on
  the same 500 dev claims; the out-of-sample ECE is the test split's, in
  Phase 7. (XLM-R's T came out 0.795: balanced class weights left it
  UNDER-confident -- the opposite of what the plan predicted.)
- **tau_abstain (FR-14) = 0.317**, by the pre-fixed criterion. It answers 60% of
  dev claims and lifts accuracy only 0.320 -> 0.353: the served arm's
  confidences are honest and flat (0.28-0.42 for almost every claim). For
  comparison, XLM-R goes 0.49 -> 0.57 at 60% and 0.69 at 24%.

### Generation: IndicBART + LoRA, behind the gate

Trained on train claims (by frozen split membership -- iterating train.json would
train on the local test split; tested) with their gold QA evidence, targets the
justifications with "according to the QA pairs" phrasing removed. bf16, 4 epochs,
loss 3.20 -> 2.64, 4.5 min, 3.70 GiB. Raw output, pre-gate, dev:

| decoding | input | faithful | chrF vs justification |
| --- | --- | --- | --- |
| **beam** (served) | retrieved passages | **0.524** | **0.237** |
| greedy | retrieved passages | 0.500 | 0.233 |
| nucleus (p=0.9) | retrieved passages | 0.408 | 0.185 |
| beam | gold QA (oracle) | 0.272 | 0.243 |
| *extractive baseline* | *retrieved passages* | *0.628* | *0.200* |
| *extractive baseline* | *gold QA* | *0.826* | *0.185* |

Beam wins on both measures, so it is served. Nucleus sampling buys variety and
pays in unsupported sentences, falling below the extractive baseline even on
chrF. No generator matches the extractive baseline's faithfulness, which copies
the evidence by construction -- that is why chrF sits beside it.

Against the plan's prediction, explanations are **more** faithful on retrieved
passages than on the gold QA they were trained with, for two measured reasons:
retrieved evidence is 8x longer (median 4,464 vs 542 characters), so the model
copies spans and copied spans are entailed; and 216-249 of 500 explanations
carry a verdict sentence ("Therefore, the claim is refuted") that no passage can
entail. The second is a limitation of the metric as CLAUDE.md defines it --
reported, not redefined. With gold QA the model also paraphrased its way into
contradictions ("Robert E. Lee was not a slave owner"), which the gate exists to
stop.

### The served pipeline, end to end

The seven Phase 5 forwards through `configs/pipeline/dev.yaml` and then through
`make serve` over HTTP:

| forward | truth | served | explanation |
| --- | --- | --- | --- |
| दिल्ली भारत की राजधानी है | true | **Supported** | generated, cites e1, e3 |
| Narendra Modi Gujarat ke mukhyamantri rahe hain | true | Refuted | gate failed -> template |
| Taj Mahal Shah Jahan ne banwaya tha | true | Refuted | gate failed -> template |
| ਲਾਹੌਰ ... ਰਾਜਧਾਨੀ ਹੈ | true | **abstained**, leaning Supported | template, by rule |
| hot water kills the coronavirus | false | **Refuted** | generated |
| नींबू पानी ... कैंसर ठीक | false | **Refuted** | generated |
| har student ko 6000 rupaye milenge | false | **Refuted** | template (see below) |

Five right or abstaining in the right direction, two true claims refuted -- both
from fact-check titles about a *different* claim on the same entity, or a
disambiguation page. Peak VRAM with every model resident: **2.51 GiB** of the
~4.9 GiB card. Warm latency 1.3-3.6 s.

**The gate passed the rumour as its own explanation.** For the Rs 6000 forward,
verdict Refuted, the explainer returned the claim itself, word for word, and it
cleared the faithfulness gate at 0.99 -- a retrieved passage asserted the rumour,
so the sentence was "faithful" to it. Served, the system would have shown the
misinformation as its explanation for refuting it. Faithful to some passage is
not consistent with the verdict: under any verdict but Supported, a generated
sentence that entails the claim now fails the gate (entailment 0.73 here).

**The first request after start-up always got the template:** the explainer
loads lazily inside the 8 s generation budget. `make serve` now sends a warm-up
request (56 s) before taking traffic, as SYSTEM_DESIGN 13 always said it should.

**Confidence bands** come from the served arm's dev reliability bins (UI_UX 7):
medium 0.40, where dev accuracy first reaches 0.5; high 0.50, where it reaches
0.75 -- on 3 claims, which is thin and said so in `app/main.py`.

### The attention figure (Unit IV)

`docs/figures/explainer_attention.png`, a dev claim chosen by a stated rule:
**73% of the decoder's cross-attention lands on the trailing `</s> <2en>` tags**
(an attention sink) and ~17% on the evidence passages. The first render left the
tags out and showed rows summing to 0.27 -- a figure hiding most of the attention
would have invited exactly the wrong reading. Reported with its caveat: attention
shows where the decoder looked, not why it wrote what it wrote. The rule-chosen
explanation also contradicts itself ("There is no evidence ... Therefore, the
claim is refuted") -- the gate's reason to exist, kept rather than swapped for a
prettier example.

### Bugs found on the way

- **IndicBART went to NaN loss under fp16** in epoch 1 (mBART-family models
  overflow fp16). bf16 for training and inference; a non-finite loss now stops
  the run at its first step.
- **transformers 5 reads `spiece.model` through protobuf**; without it, it falls
  back to a tiktoken reader and fails with an error about tiktoken. Added to the
  ML lock.
- **IndicBART's `<2en>` and `</s>` survive `skip_special_tokens`** and would have
  reached the user and been graded as words. Stripped.
- **`calibration: {}` read as off** (an empty dict is falsy). Presence, not
  truthiness.
- **`aggregate: learned` without a path did not know its stance**, and a missing
  artifact crashed start-up. The orchestrator passes the stance; a missing
  artifact degrades to the rule with a trace note.
- **Background jobs here are killed at ~30 min**, and the batch runner writes
  only at the end: the train passages run was stopped at 29 min ETA and re-run as
  two shards (`--offset`).

### For the project owner: the served stance

**SUPERSEDED the same day** -- decided as `xlmr_nli`; see the entry "The served
stance: XLM-R decides, NLI shows" below. The table is kept as the question was
put.

| | NLI (served) | XLM-R |
| --- | --- | --- |
| AVeriTeC dev macro-F1 / accuracy | 0.2135 / 0.320 | 0.2802 / 0.490 |
| vs claim-only control | significantly worse | tie |
| on real forwards (Phase 5) | reads the evidence | labels as its claim-only twin |

### Cut, and why

- **The k ablation.** D4 found that reading evidence adds nothing measurable
  over the claim prior; how many passages the aggregator reads cannot matter
  much when the passages do not move the verdict. The cached passages hold 20
  per claim, so it is a cheap Phase 7 addition if wanted.
- **The prompted-LLM comparison** -- slack-only by the plan.

### Phase 6 -- COMPLETE 2026-10-02

FR-11 to FR-16 and FR-18 are built and measured; FR-17 (explanation language)
is cut to English as decided. Served: hybrid retrieval, NLI stance, learned
aggregator, tau_abstain 0.317, floor off, IndicBART behind the NLI gate.
(Superseded later the same day: served stance `xlmr_nli`, tau_abstain 0.3835 --
next entry.)
Suite: 599 passing. The test split is untouched; its one run is Phase 7's.

## 2026-10-02 — The served stance: XLM-R decides, NLI shows

Phase 6 ended with the served stance as an open question, and the project owner
delegated it: "I just want the best results." Decided on measurements, with
every rule written down before the run it governed.

**The two candidates are good at different jobs.**

| | NLI | XLM-R |
| --- | --- | --- |
| AVeriTeC dev verdict macro-F1 / accuracy | 0.2135 / 0.320 | **0.2802 / 0.490** |
| XLM-R vs NLI, paired (24d42acb4fea) | | **+0.067 [+0.022, +0.112]** |
| accuracy at 60% coverage (abstention) | 0.353 | **0.587** |
| per-passage labels on the demo forwards | honest (10/10 Delhi leads Support) | ~all "Refutes", whatever the passage says |

Re-run under the learned aggregator, XLM-R still labelled nearly every passage of
the seven demo forwards Refutes -- the Phase 5 finding survives the new
aggregator. And those labels are not internal: the template explanation prints
them ("[2] Rajdhani Express contradicts it").

**So each model does the job it is measurably good at.** A new stance stage,
`xlmr_nli` (`stance/combined.py`), runs both: the passage labels the user sees
are NLI's, and the verdict's aggregator reads XLM-R's distribution. One more
arm was tried first, by a rule fixed beforehand -- give the aggregator BOTH
distributions, and serve that if it is at least as good as XLM-R alone. It was
not: **-0.029 [-0.063, +0.006]** (a03da2746cac), so the aggregator reads XLM-R
alone. The served verdicts equal the XLM-R arm's on 500/500 dev claims.

**Re-chosen on dev for this arm**, by the same pre-fixed rules as Phase 6:

- **tau_abstain 0.3835** -- 60% coverage, accuracy 0.490 -> 0.587, selective
  macro-F1 0.280 -> 0.311. Abstention now does something.
- **Floor off** -- 0.55 abstains 3 claims (-0.0028), 0.60 abstains 9 (-0.0074,
  CI excludes 0); 0.45 and 0.50 touch no claim for any stance.
- **ECE 0.0988 at T=1 -> 0.0690** at the fitted T=0.795.
- **Confidence bands** medium 0.40 (dev accuracy first >= 0.5: 0.52, n=148),
  high 0.60 (0.74, n=35).
- **Peak VRAM 3.56 GiB** with both stance models resident.

**What it costs, stated for the report.** On the seven demo forwards the served
config gets three false claims Refuted and abstains on two true ones while
leaning Supported -- and still refutes two TRUE claims (Modi as Gujarat CM, the
Taj Mahal) at confidence 0.67 and 0.72, inside the "high" band. That is XLM-R's
claim prior, the price of its better AVeriTeC numbers; NLI made the same two
errors at low confidence. The confident wrong refutation of a true claim is the
failure the error analysis in Phase 7 should look at first.

## 2026-10-02 — Phase 7, steps 1-4: test readiness, provenance, FR-26, FR-19

Phase 7 runs to an approved plan: **finish the code, tag `code-freeze`, then the
one test run**, pre-registered in `docs/test-protocol.md` before any test
prediction exists, covering every component's dev-chosen arm (decided with the
owner); report in Markdown; FR-19 built rather than cut (owner's call).

**1. Test readiness.** Three holes found by auditing before touching test:
- **Only scoring was locked.** `pipeline.batch` and `score_passages.py` wrote
  test predictions without asking. Both now refuse a test split without
  `TRUTHLENS_ALLOW_TEST=1`, through one rule shared with `evaluate.py`
  (`common/test_guard.py`).
- **`calibration:` re-chooses tau on the split it scores** -- on test, choosing
  on test. `calibration.tau` now reports coverage and selective scores at a
  FIXED tau (`at_tau`); the test run applies dev's 0.3835.
- **`score_passages.py` read "train claim" from `source_id`**, which says
  `train.json` for all 307 test claims (they are held out of train.json). It
  now reads the uid's split. Latent -- nothing had run on test -- and the same
  shape as the Phase 5 knowledge-store bug.
Test gold built (gitignored): AVeriTeC retrieval 307/307 (674 gold docs),
justifications 307, CheckThat normalization 1,485.

**2. The 49 "dirty tree" results.** `scripts/check_result_provenance.py`
re-hashes every input. **All 49 have byte-identical predictions and split
files.** 23 (Phase 5) reproduce their exact config_hash and were re-scored from
a clean tree: same hashes, same metrics, flag gone. The other 26 (Phases 1-4)
cannot keep their hash -- the split lock has grown since (Phase 5 added
`averitec_stance`), and the lock sha is part of the hash -- so they keep the
flag, with this explanation. Their numbers are not in doubt; their provenance
label is.

**3. FR-26 completed: romanized X-CLAIM.** The P0 requirement named a
transliterated X-CLAIM test set that was never built, so span identification had
no romanization number at all.
- `preprocess/romanize.py`: native -> informal Latin. Dakshina's train lexicon
  (most-attested human spelling), rules with schwa deletion for unknown words,
  one whitespace token to one token so span gold carries over.
- `x_claim_romanized/{dev,test}` (183 / 193): X-CLAIM's native hi/pa eval posts,
  romanized. New files only; `verify-reproducible` confirms all 21 split files
  rebuild byte for byte with the new eval rows visible to dedup.
- **How synthetic is it?** On the 33 hand-typed Punjabi pairs, run backwards
  (Gurmukhi rewrite in, what the person typed as reference): CER **0.214**
  (3f33f4e33934); rules alone 0.283 (f4374531a66c); doing nothing 0.805. A new
  config key `baseline_texts` makes "doing nothing" echo the native source.

| span token F1, same 183 dev posts | native (02c59ee296a0) | romanized (f05dd5f44b16) |
| --- | --- | --- |
| all | 0.8064 | 0.7921 |
| hi | 0.7805 (deva, n=96) | **0.7468** (n=96) |
| pa | 0.8382 guru n=76, 0.8352 deva n=11 | 0.8453 (n=87) |

Hindi pays ~0.03 for romanization; **Punjabi pays nothing** -- consistent with
Phase 3, where zero-shot tied joint on Punjabi: its span skill is cross-lingual
transfer, which does not care about script. Synthetic romanization is cleaner
than real typing, so these are lower bounds. The joint model was re-run on
native dev first: 600/600 predictions identical to Phase 3's, so the comparison
is the same model.

**4. FR-19: manipulation flags.** `manipulation/flags.py`, optional stage
`manipulation: rules_nli`, served. SemEval-2023 T3 technique names only; five by
rules (en/hi/pa, native and romanized), two by zero-shot NLI on the resident
model at P >= 0.90, at most three. Flags are computed after every verdict is
decided and only copied onto results -- tested with the stage on and off.
**Unmeasured**: SemEval data was never obtained, so FR-19 is demo-verified, as
the SRS allows for a P2.

## 2026-10-02 — Phase 7, steps 5-6: the demo page, a new served extractor, and the code freeze

**The served extractor changed (owner's call, rule fixed first).** Choosing the
"long forward" demo chip showed the served `claims: heuristic` verifying every
sentence of 4+ words: "Dosto dhyan se padho!!" ("friends, read carefully") was
checked and **refuted at 0.83, in the High band**. Measured, the rule had never
been scored on FR-7: span F1 **0.7095** on X-CLAIM dev (6debf902eac4), barely
above whole-post 0.6851, against the joint span model's 0.7463.
`claims/heuristic_span.py` keeps the heuristic's check-worthiness gate (the span
model cannot say "no claim") and keeps candidate sentences by the share of their
tokens the span model tags: span F1 **0.7374** (e1b2227b28d9). Rule fixed before
measuring: serve it unless significantly worse on AVeriTeC dev. Isolated run,
only the claims stage changed: **-0.0030, CI [-0.0115, +0.0041]**
(268b03cffbd4). Served. Every rant tried now verifies only its claim.

**Every dev verdict number is the evidence path -- and the test must be too.**
The first comparison run used the full served config and disagreed with the
served run on 28 single-sentence claims, which the extractor cannot touch. Cause:
the served run 164d2289c90b (and every Phase 5-6 verdict run) was produced
WITHOUT `--pipeline-config` -- default stages, no fact-check matcher. With the
matcher on, the fast path answered AVeriTeC claims by finding **the claim's own
source fact-check** (dev 00070: CheckYourFact on the same Fauci claim, cosine
0.95). AVeriTeC's rules exclude the source article as evidence. Measured as a
labelled diagnostic, p7_verdict_fullpipe_dev (5d4fd8d511e6): +0.0017 macro-F1 --
small, but a lookup, not verification. So the AVeriTeC verdict, dev and test, is
the evidence path with no matcher; the fast path is measured on MultiClaim. The
test protocol said otherwise in its first draft and was corrected before any
test prediction existed.

**Test commands proven on dev.** Each test command is its dev twin's with
`--split` changed; re-run on dev, all twelve reproduce their dev predictions
byte for byte (the explainer on its first 20 claims). Table in
`docs/test-protocol.md`.

**The demo page (FR-23).** The WhatsApp-styled page of UI_UX §3-§9 replaces the
Phase 1 page. `tests/test_ui_static.py` checks WCAG AA for every token pair in
light and dark -- it caught muted text on the dark outgoing bubble at 3.72:1 --
plus string coverage per locale and that no confidence cut point is hard-coded.
Rendering real `/verify` responses through `app.js` in Node found a pipeline
bug: the English template explanation was labelled with the INPUT language, so
the card marked English text `lang="hi"` and hid the "explanation in English"
note. Fixed in the orchestrator.

**The six demo chips** (`app/static/samples.json`, our own wording) were each
chosen by running candidates through the served pipeline, and
`scripts/demo_check.py` fails if one stops showing its path. **The fast path is
nearly unreachable at the served tau_match 0.90:** correct matches for natural
phrasings of well-known hoaxes scored 0.75-0.86, and even a fact-check's own
headline reworded scored 0.864; the chip that clears it (pineapple juice and
cough syrup, 0.919) is a close restatement. tau was not lowered for the demo.
Candidate runs also added a regression forward: the TRUE "Harmandir Sahib is in
Amritsar" is refuted at 0.59 -- the error analysis's first question again.

**NFR-1/2/3 measured** (`scripts/measure_latency.py`): evidence path p95 2.51 s
(budget 10), fast path p95 0.62 s (3), cold start 61 s (90), **peak VRAM 4.60
GiB** -- within NFR-3's 5.12 GiB but ~0.3 GiB from what Windows leaves usable,
now that the span model is resident.

**Cut: the k ablation** (first on the plan's sacrifice list). Reason unchanged
from Phase 6: evidence does not move the verdict beyond the claim prior (D4), so
how many passages the aggregator reads cannot matter much; the cached passages
keep it cheap for later.

## 2026-10-02 — Phase 7: the test run, error analysis, report

**The one test run** followed `docs/test-protocol.md` on frozen code
(`git diff code-freeze -- src app` is empty for every test result), run by the
project owner -- the permission system refuses the agent the test flag, as it
should. It stopped once, at #11, on a missing file: the native gold restricted
to the romanized posts had been built for dev only (the builder gained that
output after the test gold was first built). A non-metric failure; rebuilt, and
the runner resumed at #11 (rule 2). The run-time configs were untracked when
scored, so eight results carried a dirty flag; re-scored from a clean tree, all
eight kept their hash and every metric was identical to the first scoring.

**What test says, against dev:**

| | test | dev |
| --- | --- | --- |
| verdict, served (macro-F1) | 0.2622 (0c41481ee90d) | 0.2802 |
| verdict, claim-only control | **0.3085** (36e3f8e6094c) | 0.2949 |
| served vs control | **-0.0463, CI [-0.094, +0.001]** | tie |
| ECE, after / before T | 0.039 / 0.066 | 0.069 / 0.099 |
| at tau 0.3835: coverage, accuracy | 0.63, 0.500 (majority 0.567) | 0.60, 0.587 (majority 0.61) |
| retrieval Success@10 | 0.153 (BM25 0.111) | 0.214 |
| spans, joint / served | 0.7254 / 0.7220 | 0.7463 / 0.7374 |
| spans on the same posts, native -> romanized | hi 0.8151 -> 0.7473, pa 0.7394 -> 0.6789 | hi -0.034, pa +0.007 |
| matching MRR (BGE-M3 / BM25) | 0.5355 / 0.3928 | 0.5244 / 0.3826 |
| matching, hi native vs "romanized" | 0.4731 vs 0.4736 | 0.4981 vs 0.3585 |
| fast path at 0.90 | 1.7% answered, precision 0.81 | ~2%, ~0.8 |
| explanations, faithful | 0.472 (extractive 0.606) | 0.524 |
| LID accuracy | 0.9924 | 0.9892 |

**Three findings the test changed:**

1. **Reading evidence did not help the verdict -- it may have hurt.** Phase 6's
   D4 found no evidence-reading arm beats the claim-only control on dev; on
   test the served arm falls below it, nearly significantly. The cause is
   retrieval: 15.3% of test claims get a gold document into the top 10.
2. **Abstention ranks correctly but the 60% operating point is too generous**:
   accuracy rises to 0.80 at 5% coverage, but at the dev tau it stays under
   always-Refuted. Recorded, not re-tuned (that would be choosing on test).
3. **The matching romanization gap was a measurement artefact.** Profiled,
   MultiClaim's hi/latn cell is 23 Devanagari posts made Latin-majority by
   hashtags and URLs, 13 mostly English, and 17 romanized Hindi (test; dev
   23/14/20). The clean romanization measurement is the span task on identical
   posts, where test shows a 6-7 point penalty in BOTH languages (dev showed
   none for Punjabi). The report's contribution section was rewritten to say so.

**Error analysis** (`docs/error-analysis.md`; taxonomy fixed first, one
tie-break -- P > R > W > L > S > C > X > G -- added at the first two-category
case, before the Hindi and Punjabi sheets were read): English R 7, C 2, P 1;
Hindi R 4, S 4, G 2; Punjabi R 4, S 4, G 1, W 1; six hand-typed LID failures,
all code-mixing. **The confident refutations of true demo forwards are the
claim prior**: the claim-only control refutes Modi, the Taj Mahal and the
Harmandir Sahib too, and for the Harmandir Sahib every passage the card shows
is labelled Supports while the verdict says Refuted -- the served-stance
design's cost, visible. None of this appears on AVeriTeC test (0 true claims
refuted at >= 0.60; dev 3/122).

**Report and acceptance.** `docs/report.md` complete; 50 runs cited, every
number checked against its results file by `scripts/check_report_numbers.py`.
`docs/acceptance.md`: every P0 verified or verified with a stated limitation,
every cut recorded; `make lint`, `make leakage`, `make test` pass on a clean
clone (697 passed, 18 skipped for gitignored data).

**Still open, needs a human:** the native-speaker review of the Hindi and
Punjabi UI strings (`docs/i18n-review.md`) before any demo.

## 2026-10-02 — Phase 7 COMPLETE: the Hindi and Punjabi UI strings reviewed

The project owner reviewed every Hindi and Punjabi interface string
(`docs/i18n-review.md`). Applied exactly as given: 18 Hindi and 23 Punjabi
strings; every `{placeholder}` survives (checked). The main changes:
- `{publisher}` constructions made gender-neutral;
- verdict labels rephrased to say what the evidence does ("सबूत इसका खंडन करते
  हैं") -- the evidence-not-truth framing, in Hindi and Punjabi too;
- everyday UI words ("पेस्ट करें", "रुझान", "ਵੇਖੋ", "ਕਾਫ਼ੀ ਸਬੂਤ ਨਹੀਂ").

One change carried into English: the review notes "Alarming language"
misdescribes SemEval's *Loaded_Language*, and the corrected hi/pa say
"inciting" / "emotional" language, so `en.json` now reads "Emotionally loaded
language". Both locale files now record the review in `_comment`; the
"UNVERIFIED" guard in `tests/test_ui_static.py` accepts the reviewed form.
Rendering the six demo responses through `app.js` in en, hi and pa: no
unfilled placeholder, no undefined, no missing key.

**Phase 7 is complete.** Every P0 requirement is verified (`docs/acceptance.md`);
what remains is the live demo itself, after `python scripts/demo_check.py`.

## 2026-10-02 — After the test run: why the Taj Mahal was refuted, and a partial fix

The owner asked why the TRUE "Taj Mahal Shah Jahan ne banwaya tha" was refuted
(0.72, High). Traced, three causes in a row:
1. the rule-based transliterator garbled the names (तज महल शह जहन);
2. **nothing downstream read the transliteration** -- the claim text comes from
   `normalized`, which stays in Latin letters, so the free-text corpus (Hindi
   and Punjabi Wikipedia leads) was searched in the wrong script and returned
   English fact-check titles that matched "Taj Mahal" or just "Shah";
3. no passage said who built it, so the claim prior decided (the claim-only
   control refutes it too).

Owner chose fixes A + B, applied after the test run and measured on dev and
the demo forwards only (report §8a; the frozen test numbers stand):
- **A, kept.** `LexiconTransliterator` (Dakshina train lexicon read backwards,
  rules for the rest) -- rule fixed first, met: hand-typed Punjabi CER 0.4281 ->
  0.3359 (832a76d75780); plus `free_text_translit_query`, searching romanized
  free text with the claim's native-script form too.
- **B, rejected.** `free_text_coverage` (abstain when no passage holds half the
  claim's content words; 1/2 fixed first). It abstained on the well-supported
  lemon-water refutation: its best evidence is a Spanish fact-check (coverage
  0.00) and a Hindi page with an inflected verb (0.40). Word overlap cannot
  judge cross-lingual evidence. Code kept, off by default and in the served
  config.

**Outcome on the demo set:** Modi now abstains (was Refuted 0.67); the Taj Mahal
is still Refuted but at 0.57, Medium (the search now finds Hindi pages about
Shah Jahan's buildings -- including the legendary *black* Taj Mahal -- but not
the one-word-titled ताजमहल article); every other forward and chip unchanged.
Free text only, so no AVeriTeC or MultiClaim number can move.

Also: `PassthroughPreprocess` now accepts and ignores the full stage's
arguments, so a test can swap it into the served config.

## 2026-10-04 — Live search: built, probed, NOT adopted (yet)

The owner asked to put live search back in (it was cut-list item 2) to fix
confident-wrong or undecided answers on simple true facts: Modi as Gujarat CM.
Plan approved: Wikipedia (MediaWiki API) and the Google Fact Check Tools API,
opt-in per claim through a button, free text only. Built in four steps (74d1749,
1337ee8): polite cached clients (the spike was rate-limited), a live fast path
for a published fact-check of the claim, BGE-M3 relevance (works across
languages where word overlap did not), a UI button with its privacy note, live
badge and Wikipedia attribution.

**Two design facts from the spike, before building:** (1) the learned verdict
model refuted four TRUE claims even given the right Wikipedia evidence -- its
claim prior outweighs passages -- so the live path reads the NLI per-passage
labels weighted by relevance instead; (2) irrelevant pages must not count, and
cosine 0.5 separates them (fixed before the probe, not tuned on it).

**Proof the reported numbers cannot move:** with all of it in place, the AVeriTeC
dev verdict run is byte-identical to 164d2289c90b's predictions. Live search is
off unless a request asks, and never applies to AVeriTeC claims.

**The probe** (`docs/live-search-probe.md`; 40 claims, labels approved by the
owner, scoring and adoption rule fixed in the script first): offline 12 correct /
18 wrong / 10 undecided; live with both sources up (35 claims) 24 / 3 / 8.
Fifteen true claims fixed (Modi, Delhi, Lahore, Harmandir Sahib among them);
all three unverifiable claims went from a confident Refuted to "not enough
evidence". **But** three FALSE claims were called Supported (lemon water cures
cancer, the Sun orbits the Earth, Chandigarh is Himachal's capital): the NLI
model labels a passage that is about the same topic, or a fact-check headline
that restates the rumour, as Supports. The pre-registered rule -- no correct
answer may turn wrong -- fails (two did). **Not adopted: `live_search: false` in
the served config.** The button, code and tests stay.

Also: Wikipedia rate-limited 5 of 40 live runs; the pipeline kept the offline
answer and said so (as designed), the fetcher's minimum gap is now 1 s.

Open: the owner chooses between showing evidence without a verdict, a fix scored
on a fresh probe set (a fact-check's own rating as its stance; stricter
agreement before "Supported"), or leaving it off.

## 2026-10-04 — Live search: evidence only, after two probes

Continues the entry above. The owner chose "both, in order".
1. **Evidence only, served.** The button lists the relevant Wikipedia pages and
   fact-check reviews (with each publisher's own rating) and gives no verdict;
   no NLI label reaches the user, so a false "Supported" is impossible.
2. **A verdict-path fix, validated on a fresh set.** Three changes aimed at run 1's
   failures: a fact-check's stance is its publisher's rating; NLI reads the two
   sentences closest to the claim; Supported cannot stand over a refuting
   passage. Probe set 2 (35 claims, committed before the fix existed, labels
   approved by the owner) was run under the same pre-fixed rule.
   **It failed: three correct answers turned wrong**, and five false claims
   were called Supported ("Mumbai is the capital of India", "Shimla is Punjab's
   capital", ...). The claims differ from the truth by one entity and the pages
   are about the right place; the NLI model's resolution in Hindi and Punjabi
   cannot tell which capital. Diagnostic on set 1's known failures had looked
   right -- exactly why the validation set had to be fresh.

**Decision:** the verdict path stays off (`live_verdict: false`); live search is
served as evidence only (FR-28, `docs/live-search-probe.md`, report §8b). The
new hi/pa strings are machine-drafted, listed in `docs/i18n-review.md` for review.
The Google key lives in a git-ignored `.env`; a test proves it never reaches the
cache, a log or a trace. My earlier commit message for set 2 miscounted it
(35 = 15 true + 17 false + 3 unverifiable).

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

Everything planned is done. The remaining items are the owner's and are listed, in order, under "WHAT THE OWNER STILL HAS TO DO"
near the top of this file (restart the server; review the new hi/pa strings; the relatives' usability test and
`docs/usability-results.md`; demo rehearsal; read the report once; `python scripts/check_report_numbers.py docs/report.md` after any
edit). Writing and polish only: no new code, no new numbers, unless the owner asks.

Optional, all outside the frozen result: `tau_similar` 0.65; a judge that separates qualifiers ("first Indian" against "first
Indian-born woman") and answers more than 30% of claims (new pre-registered protocol on fresh claims; deferred by the owner, in
memory); IndicXlit in its own venv; a correction for the verdict model's "forwarded claims are false" prior.

**The floor to beat, per component** is superseded by the test table in
`docs/report.md` §8.

### Open items

- ~~CheckThat! 2025 Task 2~~ **Downloaded 2026-09-24.** No dataset gaps left.
  Still to build: its loader and frozen splits (Phase 3). Use
  `test_gold-*.csv`, not `test-*.csv` — the latter has no labels.
- **An accurate transliterator.** IndicXlit is ruled out in this environment
  (it would install CPU torch over the CUDA build). Options: a character-level
  seq2seq trained on Dakshina's word pairs, or IndicXlit behind a subprocess
  boundary in its own venv. See the Phase 2 entry for why it matters.
- ~~**Knowledge store train split (63.52 GB)**~~ **BUILT (Phase 5), and its
  passage vectors cached at depth 200 (2026-10-01, 5.7 GB; test 307/307, train
  2,662/2,666 -- the other four have no text).** The original note follows.
  **REQUIRED, and this line used to say otherwise.** It said the train store was "only needed if training retrieval on
  AVeriTeC". Wrong: AVeriTeC's official test labels are withheld, so this
  project's locked **test split is 307 claims carved from the public
  `train.json`** (Phase 0 decision), and their evidence pools live in the TRAIN
  store — spread across all three of its files (115 / 86 / 106 claims). **Without
  it the final reported AVeriTeC number cannot be produced at all.** Its first
  use is earlier: a learned aggregator (Phase 6) trains on train-claim evidence.
  Fits on D: (90.5 GB free on 2026-09-30); resumable; start it in the background
  well before Phase 6, since multi-GB pulls here get interrupted.
- **Knowledge store test split (40.71 GB) — NEVER needed.** Its claims have no
  public labels, so nothing downloaded from it could be scored. Of the "~110 GB"
  AVeriTeC store, 11.54 GB is in hand, 63.52 GB is required, and 40.71 GB is not.
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

### English route for the live verdict (2026-10-04): best result yet, not adopted

Built route A (owner-approved): NLLB-200 distilled 600M translates hi/pa claims
(romanized from native-script form), English Wikipedia is read (hi/pa pages via
language links), DeBERTa-v3-large NLI judges. Config `live_translate`, off in the
served config; `describe()` omits it unless on, so no hash moved. New: `preprocess/translate.py`,
`WikipediaLive.search(to_english=)`, `Orchestrator._live_stance/_english_claim`,
`scripts/live_probe.py --translate`; 773 tests, lint clean.
Findings: translation alone did NOT fix single-entity swaps (mDeBERTa still said the
Mumbai page entails "Mumbai is the capital of India", 0.99); the English large NLI does
(contradiction 0.95). It was chosen on probe set 2 pairs, so set 2 is spent for it.
Set 3 (39 fresh claims, committed before the code froze, owner-approved): run 3a was
disturbed by Wikipedia 429s (offline answers kept in 12 rows) and was re-run once,
identically, pause 8 s (both kept in `reports/`). Run 3b: live 28 correct / 9 undecided
/ 2 wrong vs offline 12 / 16 / 11; all 15 true claims gained; no regression. Rule (3)
FAILS: an unverifiable tea-stall claim refuted from a Brick Lane Market page, and a
false claim (Ganges into the Arabian Sea) Supported from Daman Ganga/Varahi pages.
Both are RELEVANCE errors, so route B (fine-tune NLI) would not fix them. Served
unchanged: evidence only. Details: `docs/live-search-probe.md` Run 3, report §8b.
New cached model: NLLB (2.4 GB) and DeBERTa-v3-large under `D:\hf-cache`.

### Entity-grounding gate (2026-10-04): 1 wrong in 38, still not adopted

Built `title_grounded` (consonant-skeleton match of every content word of a Wikipedia
title against the claim) on the English route; fact-check reviews below tau_match are
listed, not judged; a failed translation keeps the offline answer. Frozen and pushed
(`86e3098`, 788 tests) before set 4 was run. Set 4: 38 fresh claims, owner approved (the
review message miscounted 15/18; the file is 16/17/5). Run 4a hit 429s again and was
re-run once identically (both kept). Run 4b: live 18 correct / 19 undecided / 1 wrong
vs offline 8 / 14 / 16; rules 2 and 3 hold; rule 1 fails on "Kalpana Chawla was the
first Indian to travel to space" (offline Refuted by the prior, live Supported: the page
says first Indian-born WOMAN in space). Cost of the gate: 14 of 17 false claims
undecided. A first version that still judged fact-check ratings made two true claims
wrongly Refuted (reviews of other Modi stories), hence the rule. Served unchanged
(evidence only); further attempts stop here. `docs/live-search-probe.md` run 4, report
section 8b.

### Demo: Roman-Hindi chip replaced by a pre-fixed rule (2026-10-04)

The owner ran the demo. Findings: the fast-path card repeated the publisher line three
times and said "Couldn't generate an explanation" (UI bug, fixed in `app.js`, `9315ff7`);
the Roman-Hindi chip ("...6000 rupaye") was refuted High from a fact-check about a US
stimulus cheque (right verdict, evidence about a different claim, the report's error
category). The owner delegated the choice ("just need the best results"), so it was
decided by a rule written BEFORE running (`scripts/pick_romanized_chip.py`): the served
pipeline must call a romanized-Hindi candidate correctly, not abstain, and every cited
source plus the first listed one must have BGE-M3 cosine >= 0.5 with the claim. Of 14
candidates (our wording) ONE qualified: "Kal se WhatsApp ke paise lagenge" (Refuted
0.76, sources cosine 0.54-0.58; they are about WhatsApp, modestly on topic, one an
Italian "WhatsApp Gold" hoax page). The other 13 failed mostly on source relevance
(0.20-0.46), which says how rarely romanized free text gets apt evidence offline: worth
a sentence in the talk. Full table: `reports/romanized_chip_pick.json` (local). The old
forward stays in `samples.json` `regression`. `demo_check.py` prints OK.

### Live verdict shipped (2026-10-05): earned by two pre-registered measurements

How it was reached: four hand-written probe sets rejected a live verdict (wrong answers 5, 5, 2, 1), so the
question moved to FEVER dev (CC BY-SA, `copenlu/fever_gold_evidence`, read from the Hugging Face cache) with
protocols and rules committed before any claim ran. **Protocol 1** (`docs/live-fever-protocol.md`; 150 claims to
choose among V1-V3, 300 to decide): V2 (DeBERTa-v3-large and BART-large-MNLI must agree) had the fewest
false-Supported on the first set, then on the second 3 of 200 (upper 4.3%) but 78.8% accuracy on answered
claims against an 80% bar: **failed by two claims** (the protocol also had an arithmetic slip, "at most 4 of 200"
for a 5% bound, caught and corrected before any run, and was amended once, before the decision set, to stop a
verdict that answers almost nothing from passing). Reading the errors afterwards (post-hoc, said so everywhere):
22 of 32 were FEVER "not enough info" claims V2 called Refuted, mostly absurd claims false in reality. The owner
asked to ship anyway; I refused to call it a pass or to drop a worse fresh run, and offered a redesign (A+).
**Protocol 2** (`docs/live-fever-protocol-2.md`, approved before any data was drawn): 350 fresh claims, the owner
labelled the 100 FEVER-NEI claims T/F/U blind (60 false, 25 true, 15 unverifiable), gates fixed in advance:
false-Supported upper bound <= 5% (3 of 225, 3.85%), precision >= 90% with lower bound >= 85% (100/106, 94.3%,
88.2%), >= 50 correct on the 250 decidable claims (92), <= 2 false-Supported per language on a translated
round trip (hi 0/33, pa 1/33). **All four passed.** Six wrong answers listed in the protocol, causes uninvestigated.
Coverage is about 30%; caveats (FEVER-style claims, DeBERTa saw FEVER-style data, round trip, one labeller) travel
with the numbers.

Shipped (it ships labelled "validated on a pre-registered fresh set", with both protocols reported): the two-model
agreement in `Orchestrator._live_pass`, `live_verdict` and `live_translate` on in `configs/pipeline/dev.yaml`,
the card's notes (`live_verdict_basis`, `live_validated`, `live_no_verdict`; hi/pa NOT YET REVIEWED), report §8b,
SRS FR-28, SYSTEM_DESIGN §15, UI_UX §5 and §11, acceptance matrix. Harness: `scripts/live_fever.py`
(collect, score, variants, select, decide), `scripts/live_ship_check.py` (the shipped cards equal the measured
V2 predictions on all 188 compared claims, en/hi/pa), `src/eval/metrics.false_label_rate` + Wilson interval,
FEVER splits `fever_{select,confirm,confirm_sub,fresh,fresh_sub,fresh_truth,fresh_sub_truth}`.

**Found while shipping, fixed:** resident, the three live models (NLLB 1.62, DeBERTa-large 0.81, BART-large 0.75
GiB) pushed the peak to 6.20 GiB on a 6 GiB card (NFR-3: 5.5; real ceiling ~4.9), spilling into shared memory.
They are now held in CPU RAM and moved to the GPU one at a time (`offload=True`, same fp16 weights, identical
cards): peak 3.81 GiB, a live click median 2.21 s, p95 3.17 s. They load in a background thread after the
server is ready so cold start (NFR-2) is unaffected. `make serve` itself was broken in PowerShell and cmd (a
Unix-only environment variable); `scripts/serve.py` replaces the line.

Also this session: the three Hindi/Punjabi live-search strings reviewed and applied (3 corrected, 7 kept); the
fast-path card no longer repeats the publisher line (UI); the Roman-Hindi demo chip replaced by the pick of a rule
written before running 14 candidates (`scripts/pick_romanized_chip.py`; only one qualified, which says how rarely
romanized free text gets apt evidence offline).

### A card for ordinary people (2026-10-05)

The owner: the app is for general people (parents, grandparents), and the answers had too many things.
Plan approved with all recommendations (answer in the message's language with a language switch;
Listen and Copy a reply in; technical card kept behind Details; relatives will test).
Built, front end only (`app/static/{app.js,styles.css,index.html,i18n/*}`; no pipeline, API or number changed):
the plain card (verdict word, one reason, what to do, closest sources, persuasion warning in words, the
claim checked, Listen, Copy a reply, the live button in plain words), the technical card moved verbatim
into a closed Details fold, a language switch that re-renders every answer, the examples folded away,
17 px type and larger tap targets. Honest wording: "probably", "the sources I found"; offline sources
are labelled "closest sources I found" because they are sometimes only loosely related (the Roman-Hindi
chip's US stimulus fact-check); a live verdict says nothing about how sure it is (uncalibrated).
Checks: `tests/test_ui_static.py` (64: every string in every language, no jargon in the plain strings,
tap targets), `scripts/ui_plain_check.js` (24 renders over the demo cards plus two live cards in en/hi/pa:
headline, reason, action, no technical words outside Details, word budget, Listen and Copy, reply in the
card's language), the older render checks updated. New hi/pa strings (55, machine-drafted) await the
owner's review (`docs/i18n-review.md`, last section). The relatives' test is specified in
`docs/usability-test.md` (questions and pass bars fixed before testing); results go in
`docs/usability-results.md`. Not yet checked in a real browser by me (no browser tool): the owner looks.

**Plain card, same day, after the owner's review.** The owner reviewed the 55 hi/pa strings: 54 applied as given.
Two issues recorded for them in `docs/i18n-review.md`: `plain.flags` kept as drafted because the reviewed sentence
("... {list} करने के लिए उकसाने ...") does not fit the reviewed infinitive technique phrases, and the Punjabi
`plain.sure.High` and `plain.sure.Medium` came out identical. New rule from the owner: a forward typed in Latin
letters ("Kal se WhatsApp ke paise lagenge") is answered in English, and Hindi or Punjabi answers only when the
message itself is in Devanagari or Gurmukhi (`cardLang` in `app.js`; the language switch still overrides;
checked in `scripts/ui_plain_check.js`).

**Plain card, the three open points decided by the owner (same day):** `plain.flags` kept as drafted; Punjabi
`plain.sure.Medium` made distinct ("ਮੈਨੂੰ ਠੀਕ-ਠਾਕ ਭਰੋਸਾ ਹੈ।"); the helper made gender-neutral
(`plain.reason.abstained_*` and `plain.reply.check` reworded in hi and pa). All 55 plain-card strings are now
reviewed. Next: the relatives' usability test (`docs/usability-test.md`).

**Language buttons, fixed (2026-10-05).** The owner asked why there were three language buttons and why a Punjabi
(Gurmukhi) forward came back in English. The buttons (EN / हिं / ਪੰ) were meant to switch the page, but pressing any
of them also locked every answer to that language for the session (and EN looks selected by default on an English
browser), which is the likely cause. They now change only the page (labels now carry the full language name), and
the answer always follows the message's own language and script; `?lang=` no longer forces the answer either.

**A bug found while chasing that (2026-10-05): Unicode forms.** The same Punjabi chip sentence typed with the
precomposed letter ਫ਼ (U+0A5E) instead of ਫ + nukta (U+0A3C) gave NEI instead of Refuted: the pipeline never
normalizes text, so two forms of one text are different inputs. Fixed at the server's door only
(`app/main.py`: `unicodedata.normalize("NFC", ...)` before `orch.verify`, with a test in `tests/test_api.py`), so
the evaluation runs, which never come through the API, and every reported number are untouched. Verified on the real
server: both forms now give Refuted at 0.43. The evaluation pipeline itself still does not normalize (frozen); it is
a limitation worth a sentence if a reviewer asks why a retyped claim can change an answer.

**Language buttons removed and the earlier look restored (2026-10-05, owner's request).** The owner never wanted
the three language buttons (they were in my plan as "comfort for older readers", approved only in general) and
preferred the earlier sizes. Removed: the buttons and their code, and the larger type (15 px), the wider column
(440 px) and wider bubbles (88%) are back, with the plain card's elements scaled to match. Kept as built: the plain
card, the "Try an example" fold, Details, Listen, Copy a reply. The page language follows the browser or `?lang=`;
the answer follows the message's script. The tap-target test was relaxed (buttons at least 2 rem) and a test now
guards that no language buttons come back.

### The offline guess is no longer shown as an answer (2026-10-05, after the owner's own questions)

The owner tried their own questions and said the answers were not correct. They were right: "Has NEET paper ever
been leaked?", "Has JEE paper been leaked?" and "Methyl Phenidate is good medicine for ADHD" all came back "Probably
FALSE, I am quite sure" with unrelated or off-claim sources (a UK Cabinet Office letter, the Titan submersible,
fact-checks about milk and sugar); "Paris is the capital of France." came back Refuted (0.49); "JEE paper leaked"
came back "nothing to check". The cause is the section 1 finding: the offline evidence path mostly reflects "forwarded
claims are usually false" (on the 350 fresh claims of the live protocol it said Refuted for 122 of 125 true claims
and never Supported, results/e3044f2aa461.json). My plain wording ("the sources I found say this is not right", "I am
quite sure") made it worse. Approved by the owner and built (UI plus one optional flag; no pipeline behaviour, API
default or reported number changed): (1) an offline evidence-path result is shown as "Hard to say: I couldn't find a
source that checks this exact claim", with the closest things found, the live button and its reason, and the
system's lean only inside Details marked unreliable; verdicts are shown only for a matched fact-check (fast path) and
the live check that passed protocol 2; (2) "not a claim" now says "I didn't find a claim to check" and offers
**Check it anyway**, which sends `force_claim: true` (new optional field of `POST /verify`; `Orchestrator.verify(...,
force_claim=)` skips the claim gate and checks the whole text as one claim; two tests); (3) the card never says "the
sources I found" when it shows none. The claim gate itself is untouched (frozen): it refuses short fragments without a
number, name or full verb ("JEE paper leaked"), and accepts "JEE 2025 paper leaked". New hi/pa strings (7) await review.
Side effect on the demo: the Roman-Hindi and long-forward chips are now honest "Hard to say" cards; the fact-checked
chip and live results still show verdicts.

### A "similar fact-check" card (2026-10-05, approved by the owner)

Why: 30 typical hoaxes sent to the owner's server: 29 came back Refuted by the evidence path (a guess, now
hidden), only 1 reached the fast path, yet the matcher alone found a relevant published fact-check for most of them at
scores 0.55 to 0.77 (WhatsApp charging -> BOOM 0.735; Hindi version 0.668; salt-water gargling -> CheckYourFact 0.767;
lemon water -> THIP 0.715; Hindi microchip -> AajTak 0.701). Built: `ClaimResult.similar_match` (additive; set when
tau_similar <= best score < tau_match; changes no decision), `PipelineConfig.tau_similar` (off by default, kept out of
the config hash), the card ("A similar claim was fact-checked ... {publisher} rated it False ... may not be the same
message", link, reply with the link; strings en/hi/pa, hi/pa not yet reviewed), 6 orchestrator tests, a UI render check.
**The threshold rule was fixed before the dev curve was read** (`docs/similar-factcheck-protocol.md`): lowest dev
threshold with precision >= 0.70 = 0.8517, rounded up to **0.86**. **It disappoints, and the log says so:** my proposal
quoted TEST numbers (70-72% right at 0.75-0.81, 10-24% of posts); the DEV curve that governs is lower (65-69%), so the rule
gives coverage 4.8% of real posts (precision 0.742) and the card shows for none of the 30 hoaxes. A table of
thresholds (0.86 / 0.75 / 0.70 / 0.65: coverage, precision, hoaxes served) is in the protocol; choosing a lower one is the
owner's product decision (a one-line config change), recorded as post-hoc if made. Test check at the chosen threshold
(stored predictions): 0.768 precision, above the 0.60 floor.

### "Be careful" wording, tau_similar 0.70, unrated suggestions (2026-10-05, the owner's call)

The owner objected that "Hard to say" everywhere makes a poor demo and a poor product, and asked for the old answers back.
Declined to bring back "Probably false" (the old path says false to everything: 122 of 125 true claims in the test, Paris, methylphenidate),
and explained that its demo "successes" were hoaxes, which are false. Offered and approved: (1) tau_similar **0.70** (the
owner's product decision after seeing the table; the rule gave 0.86; recorded as post hoc in `docs/similar-factcheck-protocol.md`);
(2) the guess that leans false is shown as **"Be careful with this one: I couldn't find a source that checks this exact claim.
Most messages like this turn out to be false."** (amber), which is all the guess ever knew; other leans stay "Hard to say".
Found while testing: `top1` drops a best match whose rating cannot be mapped (the garlic fact-check, 0.756), so the suggestion
now uses `FactCheckMatcher.similar` (new; `top1` and all evaluation untouched) and can be shown without a rating
(`SimilarMatch`, 2 more tests). The owner's offline question "could a claim ever be true without checking online?": only
via a matched fact-check rated true or the Lahore-style lean; Supported was never said in 350 claims. Result on the 30 hoaxes
through the real preprocess, claim gate, extraction and matcher (CPU): 1 fast-path verdict + 6 similar cards = 7 of 30
get a real source, 22 get the careful warning, 1 is refused by the gate. New hi/pa strings await review.

### Two card fixes from the owner's own questions (2026-10-05, approved)

1. **"Check it anyway" on a greeting no longer says "Be careful".** The claim gate had refused "Good morning, stay blessed", the reader overruled it,
   and the offline guess (which leans false for nearly everything) produced the warning. A checked-anyway card now says "Hard to say"; the
   "Look this up online" button on it also sends `force_claim` (before, it asked for the same message without the flag, got "not a claim" back,
   and said "Online search isn't available right now").
2. **A similar fact-check keeps leading the card after a live look-up that still cannot decide.** Pineapple juice in Roman Hindi scored 0.722
   against the newsmeter fact-check (the English wording scored 0.919, above the 0.90 fast-path bar), so there was no verdict; the live look-up
   found nothing decisive and the card fell back to "still hard to say" with the fact-check only as a listed link. Now the title, reason and
   "Copy a reply" say "newsmeter looked at something similar ...", and the fact-check is not listed twice. Frontend only (`app/static/app.js`,
   `showsSim`, `_forced`); no backend, threshold or number changed. Checks added to `scripts/ui_plain_check.js` (`forced_greeting`, `live_similar`).
   Not done, and not approved: lowering the fast-path bar for Roman script (needs a new pre-registered measurement on fresh Roman-Hindi claims).

### "Be careful" survives an empty online look-up (2026-10-05, the owner's point)

A card that said "Be careful with this one" turned into "Hard to say" after "Look this up online" found nothing, which read as the app
becoming less sure for no reason. Now, when the card was a "Be careful" before the look-up and the look-up still cannot decide, it stays
"Be careful" with the reason "I looked online too and still couldn't find a source that checks this exact claim. Most messages like this
turn out to be false." (`plain.reason.careful_live`, hi/pa machine-drafted, added to the review sheet and the `_comment`). Same finding as
before, not a new verdict; a checked-anyway greeting and a card with a similar fact-check keep their own wording. Frontend only
(`_careful` set in `searchLive`); check `live_careful` added to `scripts/ui_plain_check.js`.

### A greeting is not offered a check (2026-10-05, approved plan part 2)

"Good morning" reached a card only because the reader pressed "Check it anyway" and then "Look this up online", and the online page
("Solemnity of Mary") was irrelevant. Now `claims.heuristic.why_not_claim` says why the gate refused a text (`greeting`, `too_short`,
`no_content`; `ClaimResult.gate_reason`, NotAClaim only), `force_claim` is ignored for a greeting (a message that is only greetings, blessings,
chain requests or emoji), and the card says "Just a greeting ... nothing here to check" with no "Check it anyway" button. A fragment like "JEE paper leaked"
keeps the button. The gate itself (`is_check_worthy`, and so every claims-stage number) is untouched. New strings `plain.greeting_title`,
`plain.greeting_note` (hi/pa machine-drafted, in `docs/i18n-review.md`). Note: "Happy Diwali everyone" passes the gate (4 words; the greeting
pattern does not know festivals), unchanged and out of scope. Tests: 849 passed (run with CUDA_VISIBLE_DEVICES="" because the owner's server holds the GPU).

### The word view: "Which words mattered?" (2026-10-05, approved plan part 1)

Built after the owner asked how the project compares with the original goal (real-or-fake plus the words that influenced the
decision). `docs/word-highlight-protocol.md` (rule fixed first, commit dff4112) -> `src/explain/` (occlusion helpers, `explain_words`),
`NLIStance.score_pairs` reused, `POST /explain_words`, `PipelineConfig.word_view`, `Passage.premise` and `ClaimResult.claim_en` (live
only), `eval.metrics.word_faithfulness_metrics`, `scripts/word_faithfulness.py`, the card button and strings (hi/pa machine-drafted,
in `docs/i18n-review.md`). Run once on the CPU against the stored `fever_fresh` captures (reports/word_faithfulness_run.log):
**results/4095b565e764.json: win rate 0.908 (89 of 98), mean drop top 0.665 vs random 0.326 (ratio 2.04, bar 2.0: a narrow pass),
bottom 0.017: all three gates passed, so `word_view: true` is served.** 30 of 130 verdict claims had fewer than six words and 2 had fewer
than three helpful words; both counts are in the result. A 3-claim smoke run was made before the real run (its ratio was 1.98; it
decided nothing and wrote no result). Not done: a fast-path word view (needs its own protocol). The button appears only after the
owner restarts the server (the backend has a new route). Test suite: 860 passed, 9 skipped, 2 deselected (CUDA hidden because the owner's server holds the GPU; one earlier whole-file run of `tests/test_orchestrator.py` crashed with a Windows access violation under memory pressure, each test passed alone and the full suite passed afterwards).

### "Be careful" decided by the message, not by the model's lean: tried, NOT adopted (2026-10-05, owner-approved build)

The owner noticed that the English "Drinking lemon juice can cure cancer but hospitals don't reveal this" got "Hard to say" after a live look-up
while the same claim in Roman Hindi got "Be careful": the tone depended on the offline model's lean (NEI vs Refuted), a poor signal.
`docs/careful-rule-protocol.md` fixed rule R before any measurement (hoax-shape cues in `src/manipulation/hoax_cues.py` plus the existing
pressure-technique rules; gates: at most 15% false warnings on true AVeriTeC claims and at most half the lean rule's share, at least 15% of
false AVeriTeC claims and 20 of 30 typical hoaxes warned). Run once (`scripts/careful_rule_check.py`, results/e165f84eb4a9.json):
2.5% false warnings (the lean rule: 24.6%), but only 6.6% of false claims and 18 of 30 hoaxes warned: **two gates failed, R is not
adopted, the served wording is unchanged, the cue lists were not tuned.** Nothing user-visible changed. Open choices for the owner (each is a
new protocol or a product decision): a revised cue list tested on a fresh set (the whole-word plural miss is one known cause), or dropping the lean
from the tone entirely so every unverified claim says "Hard to say". Tests added: `tests/test_careful_rule.py`.

### "Why" quote on a live true/false answer (2026-10-05, owner's request; trial, one commit)

A live Supported or Refuted card now quotes the source sentence the answer rests on ("Why: this is what the source says: "...""), picked in the
browser from the passage that agrees with the verdict (highest stance score) as the sentence sharing the most words with the claim.
Extractive on purpose: nothing is generated. Checked on real live answers (methylphenidate for ADHD; "Everest is not the tallest mountain").
Fast-path answers get none: the index holds only the fact-check's headline, and fetching its page would break the offline path. Frontend only
(`sourceQuote`, `plain.why.*` strings for en/hi/pa, hi/pa in the review sheet, a render check). **The owner is trying it; to remove it, revert this commit
(see the commit hash in `git log`: "Why quote").**

### "Why" on a fact-checked (fast-path) answer: measured, NOT shipped (2026-10-05, owner request)

The owner asked for a "why" on every FALSE answer, without a button. Live true/false answers already quote their source sentence (commit 1c8d158).
For a fast-path answer the index holds only the fact-check's headline, so `docs/factcheck-lead-protocol.md` (rule and 70% gate fixed first, commit c78ecfa)
tested reading the article's opening paragraph automatically (one GET of the public URL, no message text sent). `src/retrieval/live/factcheck_lead.py`,
`scripts/factcheck_lead_check.py`, results/39860deeb1d8.json: **36 of 60 = 60%, below the 70% bar, so it is off and not wired into the card.** AFP desks mostly fail, and
the leads that work usually restate the claim, not the reason. Left in the repo as a documented negative result (module, 6 tests, script). Options if the owner
still wants it: a per-publisher extractor on a fresh sample (new protocol), or accept that a fast-path card shows the fact-checker's headline as its explanation.

### "Why" on a fast-path answer, take 2 (finding sentence): also NOT shipped (2026-10-05)

The owner said the pineapple card still had no why. `docs/factcheck-finding-protocol.md` (rule, cue list, 70% gates, my labelling rule fixed first, commit d7acd0f)
tested taking the first sentence that states a finding, on a fresh 60 (seed 43, disjoint from take 1). `scripts/factcheck_finding_check.py`, results/9e209d11fc4d.json:
**27 of 60 = 45% extracted, gate 1 failed, feature off.** Both takes failed because most publishers' pages (boomlive, checkyourfact, AFP) give a plain GET nothing usable.
Options, each a new protocol and probably a headless-browser dependency: per-publisher extractors, or store one-line summaries when the fact-check index is built.
The pineapple card therefore still shows the fact-checker's headline only. Unchanged: live true/false cards still quote their source sentence (1c8d158).

### "The sources disagree" wording after a live look-up (2026-10-05, owner approved)

"Mount everest is not the tallest mountain above sea level" got the generic "Be careful ... couldn't find a source that checks this" although the trace showed
two Wikipedia pages read in opposite directions (both models: Conflicting; no verdict by the two-model rule). Now `ClaimResult.sources_disagree` is set when both
models read the sources as Conflicting and no verdict is shown, and the card says "The sources I found disagree with each other on this one. Here is what I found."
under "Hard to say" (not the warning). Wording only: no verdict, threshold or number changed. `plain.reason.sources_disagree` (hi/pa machine-drafted, in the review sheet),
2 tests in `tests/test_live_pipeline.py`, check `live_disagree` in `scripts/ui_plain_check.js`. Needs a server restart (backend field).

### The owner's review of the 33 newer hi/pa strings (2026-10-05)

12 corrections applied as given (lean_note, plain.none_title pa, related_label, similar.label, similar.rating.NEI hi, similar.reason pa, greeting_title/note pa,
words.hint/none/unavailable/loading), 21 kept; placeholders preserved, the `_comment` notes for the reviewed sets replaced by the review note, and
`docs/i18n-review.md` records the outcome. **Still NOT YET REVIEWED: `plain.why.label`, `plain.why.english`, `plain.reason.sources_disagree`** (added after the sheet went out;
if the owner's 33 included them, remove the two remaining notes in hi.json and pa.json `_comment`). The render check's Punjabi greeting pattern now matches "ਸਲਾਮ-ਦੁਆ".

### The desktop workspace, the proof desk (2026-10-05, branch `ui-restyle`, owner's request: "a proper webpage ... for laptop/desktop")

The owner found the first restyle (a refined phone column) "nothing special" and asked for a real desktop page. Decisions (asked, not assumed): full desktop
workspace, confident and editorial, replace in place. World: a newspaper proof sheet marked by an editor; cobalt rail, newsprint desk, system serif for display
and quotes; signature move = the markup (verdict word stamped on, pencil stroke drawn under it; dashed and still for abstained). Phone widths (under 1100 px)
keep the earlier WhatsApp-style column on purpose. Frontend only: `app/static/{index.html,app.js,styles.css}`, no i18n edits, no new copy. Process: PRODUCT.md and the
direction contract (`.impeccable/surfaces/app-static-index-html.md`; the owner's pinned direction beat the concept roll, seed c4ac5c88), build, one detector run
(clean after advisories fixed), screenshots at 1100, 1280, 1360, 1440, 1920 and 390 in light and dark in en, hi and pa (real-time Chrome DevTools captures; no horizontal
overflow at any width), `impeccable-finish-reviewer` (disposition fix: Indic leading, glyph icons, verdict scale, nested frames, microtext, proof-sheet placeholders, sticky
forward; all applied, one regression it found, a sticky quote overlapping the card in the stacked layout, fixed), `impeccable-documenter` (`DESIGN.md`, `.impeccable/design.json`).
Not done: the phone world was not moved to the cobalt identity (owner pinned it), and `/review-animations` can only be run by the owner. `make lint` and `make test` (875 passed) pass.
