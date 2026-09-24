# Current phase and what is in scope

Pointer file. The reasoning lives in [build-plan.md](build-plan.md); this says
only where the project is right now, so a session can be oriented in ten
seconds without reading the whole plan.

**Update the "Current phase" line at the start of every session.**

> The running narrative — what was built, what was decided, why — lives in
> [project-log.md](project-log.md). This file is just the scope pointer.

## Current phase

**Phase 4 IN PROGRESS — claim matching and the fast path (FR-8).** Phase 3 is
complete: both requirements measured against baselines, the ablation replicated,
and its four verification gaps closed on 2026-09-24, the last of which turned
FR-6 from unsolved into partially solved.

Phase 4 was planned as "wire BGE-M3 behind `tau_match`". It is not that. The
bi-encoder ranks well (MRR 0.5244) and **scores badly**: a correct top-1
averages cosine 0.7239 and a wrong one 0.6500, so at τ=0.90 the fast path fires
on 1.7% of posts and still cites the wrong fact-check 18% of the time. The work
is a reranker, plus a harness task that can see a decision at all.

The clock is **14 days**. **Days 1-4 are done.** Phase 1 shipped the vertical
slice; Phase 2 shipped the language layer and the native-vs-romanized table,
which is the research contribution. Code freezes at the end of Day 12.

**The FR-26 hand-typed forwards arrived early** — 100 rows, ahead of their
Day 11 deadline — so they are already a measured eval set rather than a risk.

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
| Frozen splits | `data/splits/` | averitec 2666/500/307 · x_claim 4472/600/571 · multiclaim 25137/3153/3156 |
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

## Phase 2 results (Days 2-3) — the floor for everything after

**The deliverable: native vs romanized.** MultiClaim dev, MRR, Hindi
(n=737 native / 57 romanized):

| rung | native | romanized | gap |
| --- | --- | --- | --- |
| TF-IDF | 0.0379 | 0.0877 | **-0.0498** |
| Word2Vec | 0.0618 | 0.0581 | 0.0038 |
| MuRIL | 0.1218 | 0.0439 | 0.0779 |
| LaBSE | 0.3648 | 0.1926 | 0.1722 |
| **BGE-M3** | **0.4981** | **0.3585** | 0.1396 |

Romanized Hindi runs at **72% of native** under BGE-M3. TF-IDF's gap is
*negative* because romanized Hindi shares Latin characters with a largely
English fact-check corpus while Devanagari shares none — the only rung where
romanizing helps, and for a reason unrelated to understanding.

**The embedding ladder**, MultiClaim dev, 3,153 queries over 78,077
fact-checks:

| rung | MRR | R@10 |
| --- | --- | --- |
| random floor | 0.0002 | 0.0008 |
| Word2Vec (in-domain) | 0.0915 | 0.1197 |
| MuRIL | 0.1127 | 0.1369 |
| TF-IDF | 0.2311 | 0.3045 |
| LaBSE | 0.3216 | 0.4170 |
| **BGE-M3** | **0.5244** | **0.6688** |

**TF-IDF beats Word2Vec and MuRIL.** Without the lexical rung in the table,
MuRIL's 0.1127 would have read as a result instead of a warning.

**Language ID (FR-3)** and **transliteration (FR-5)**:

| | script heuristic | fastText | hybrid |
| --- | --- | --- | --- |
| MultiClaim hi/latn (n=57) | 0.0000 | 0.3158 | **0.7368** |
| hand-typed forwards (n=100) | 0.0000 | 0.0000 | **0.8500** |

| transliteration, 33 Punjabi pairs | CER | WER |
| --- | --- | --- |
| identity (do nothing) | 0.8518 | 0.9290 |
| rule-based, real language ID | 0.4281 | 0.7253 |
| rule-based, oracle language | 0.3810 | 0.7130 |

### The finding that should drive Phase 3+

`docs/figures/tsne_parallel_claims.json`, `script_confound`. Mean cosine between
**unrelated** sentences under LaBSE:

    unrelated hi-native   vs unrelated pa-native       0.3773
    unrelated hi-native   vs unrelated hi-romanized    0.3856
    unrelated pa-native   vs unrelated pa-romanized    0.4553
    unrelated hi-ROMANIZED vs unrelated pa-ROMANIZED   0.6900  <--

Two sentences with nothing in common, in two different languages, score 0.6900
because both are in Latin letters. The same sentence in native and romanized
form scores 0.5613. **Romanization forms a cluster of its own, and it is a
stronger signal than content.** That is why romanized retrieval underperforms.

It also predicts the fix and then rules out the cheap version of it:
transliterating out of Latin script should help, but doing it with the
rule-based transliterator *hurts* — Recall@10 on the hi/latn cell falls
0.1988 → 0.1199 — because a CER of 0.38 lands the query in the wrong place.
**An accurate transliterator is the highest-value thing to build next**, and
there is now a number saying so rather than an intuition.

Second-order caveat, recorded so it is not misread: the hand-typed pairs score
a *higher* native-vs-romanized cosine (0.7942) than Dakshina's (0.5613-0.6298).
That is not evidence that real typing is easier. It is code-mixing — "KYC",
"UPI", "48" survive verbatim into the Gurmukhi version. Shared-Latin-token
overlap is 0.0513 for the hand-typed pairs against 0.0119-0.0173 for Dakshina,
and it is recorded beside every cosine in the JSON.

## Phase 3 results (Day 4) — the floor for Phase 4 onward

**FR-7 span identification.** Token F1 on X-CLAIM dev, XLM-R-base + LoRA:

| arm | overall | en/latn | hi/deva | pa/guru |
| --- | --- | --- | --- | --- |
| whole_post_span | 0.6851 | 0.6647 | 0.7385 | 0.7445 |
| mono-en | 0.7106 | 0.6911 | 0.7089 | 0.8027 |
| mono-hi | 0.7053 | 0.6507 | **0.7881** | 0.8352 |
| mono-pa | 0.7175 | 0.6990 | 0.7375 | 0.7953 |
| zero-shot | 0.7370 | 0.7055 | 0.7811 | **0.8426** |
| **joint** | **0.7463** | **0.7232** | 0.7805 | 0.8382 |

Joint beats every monolingual arm — X-CLAIM's own finding, replicated. Two
things the average hides: the baseline is **harder** to beat in Indic than in
English (0.7445 pa/guru vs 0.6647 en/latn, because Indic posts are more
claim-dense), and **zero-shot ties joint on Punjabi having never seen a Punjabi
example**, so Punjabi performance is almost entirely cross-lingual transfer.

**FR-6 check-worthiness: solved by the arm that was trained on nothing.**
macro-F1 on the hand-typed 100, whose majority baseline is 0.4595:

| arm | derived dev (n=963) | hand-typed (n=100) | real negatives caught |
| --- | --- | --- | --- |
| heuristic (rules) | 0.4217 | 0.4595 | 0/15 |
| xlmr (trained classifier) | **0.7222** | 0.4536 | 0/15 |
| **zero-shot NLI** | 0.5478 | **0.5938** | **7/15** |

Deriving check-worthiness from the span model is structurally impossible:
X-CLAIM's every post contains a claim, so that model has never seen the negative
class. A classifier trained on derived negatives learns that set and transfers
nothing. Zero-shot NLI has no training distribution of ours to be skewed by, and
is the only arm above the baseline — at the cost of rejecting **18 of 85 real
claims**, which is the number to quote beside it.

**The two eval sets rank the arms in opposite orders**, so the derived set
cannot be used to choose an operating point. **~100 more real no-claim messages
is still the top human task**, now in order to choose a threshold rather than to
find out whether the problem is solvable.

**Normalization is not extractable**: chrF 0.2835 against a longest-sentence
baseline of 0.2875, because only **4.3%** of CheckThat references appear
verbatim in their post. That is the Phase 6 abstractive case, made with a number.

## Next: Phase 4 — claim matching (Days 5-6)

The fast path: a post matching an existing fact-check closely enough skips
retrieval. Phase 2 already built and scored the machinery (BGE-M3 over 78,077
fact-checks, MRR 0.5244), so this is mostly wiring it behind `tau_match` and
choosing that threshold.

**Decision due Day 5:** demo corpus composition (`SYSTEM_DESIGN.md` §14).

### Needs a human — I cannot do these

- ~~**~100 hand-typed romanized forwards (FR-26, P0).**~~ **DONE, Day 3.**
  100 rows, 64 hi / 36 pa, all Latin script, 15 deliberate no-claim rows, and
  33 Punjabi rows carrying a matched Gurmukhi rewrite. Ingested as
  `data/splits/handtyped/dev.jsonl`; the messages themselves stay in gitignored
  `data/raw/`. Leakage-clean against all four datasets, and checked directly
  against the LID classifier's training pool (0 verbatim, 0 substring).
- **Native-speaker review of `app/static/i18n/{hi,pa}.json`** before any demo.
  Those strings are unverified placeholders and are marked as such in the files.

### Open, not blocking

- ~~MultiClaim access~~ **GRANTED and ingested.** 25,137 / 3,153 / 3,156
  train/dev/test. The Phase 4-5 swap rule is moot. It also gives Phase 2 the
  multilingual retrieval task the embedding comparison needs.
- ~~IndicXlit spike~~ **RUN, Day 3. Ruled out**, and not for the expected
  reason. fairseq 0.12.2 needs MSVC build tools, which is fixable — but
  resolving `ai4bharat-transliteration` also pulls `tensorflow` 2.21, `tf2crf`,
  `urduhack` and **`torch` 2.14, the CPU build**, which would silently replace
  the CUDA torch every other stage depends on. A transliterator must not cost
  the project its GPU. If it is wanted later it goes in its own venv behind a
  subprocess boundary, or through WSL. The spike took 43 seconds.
- ~~CheckThat! 2025 Task 2~~ **Downloaded and split.** No dataset gaps left.
- **Real VRAM is ~4.9 GiB, not 5.5 GB.** Windows reserves ~1 GiB of the 6 GiB
  for the desktop. NFR-3's ceiling is optimistic; see `environment.md`.
- ~~**`hf.co`, not `huggingface.co`.**~~ **Withdrawn.** That was a transient
  observation reported as a property of the hostname. Re-measured at 5/10
  against 4/10 — neither is reliably better. The real lesson is **resume, don't
  retry from zero**: every large download in `scripts/` uses HTTP Range, and on
  Day 3 that carried 9.6 GB (fastText, Dakshina, MuRIL, LaBSE, BGE-M3) with no
  manual intervention.
- **`uv` can vanish.** It was absent from this machine on Day 3 and the venv
  still worked, so nothing failed until something needed installing. Reinstalled
  (0.12.18). If `make setup` reports `uv: command not found`, that is this.
- **`fasttext-wheel` 0.9.2 is broken under NumPy 2.** Its `predict()` ends in
  `np.array(probs, copy=False)`, which NumPy 2 raises on instead of copying.
  `src/preprocess/lid.py` calls the C++ predictor directly to get round it. Do
  not "simplify" that back to the documented API.

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
