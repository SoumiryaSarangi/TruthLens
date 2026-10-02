# Test protocol — the one test-split run (Phase 7)

**Written for:** whoever reads the final numbers, to check they were not chosen
after looking.

**Status:** pre-registered. This file is committed, with every config below,
**before any test prediction exists**. The run happens on the commit tagged
`code-freeze`, so every reported test number reproduces from the final code.

## Rules

1. **Nothing is chosen on test.** Every arm, threshold, temperature, k and floor
   below was chosen on dev, with the run that chose it named. τ_abstain is
   applied as a fixed number (`calibration.tau`), never re-chosen; the harness's
   operating point is reported beside it only to show where a test-chosen τ
   would have landed.
2. **Each config is scored once**, with `TRUTHLENS_ALLOW_TEST=1` and a `notes:`
   line saying it is the final run. A re-run is allowed only for a crash, a
   harness refusal or a bug that is not about the metric (a missing file, a
   path), and is recorded in the project log with its cause. A re-run because a
   number looked wrong is not allowed: a wrong-looking number is investigated
   and reported.
3. **Every model row has its baseline in the same table**, as on dev.
4. **Test predictions are not used for anything else** — no threshold, no
   feature, no error-analysis-driven change ships after them. Error analysis on
   test happens after the run and changes only the write-up.
5. **What would make a number invalid** (asked before running, as for every
   experiment): a stance or aggregator model that saw a test claim (checked:
   the stance models train on `averitec_stance/train`, 0 of whose parent claims
   are among the 307 test claims; aggregators train on train claims and fit T
   on dev); a test claim read from the wrong knowledge store (the runner picks
   the store from `source_id`; test claims live in the TRAIN store); a test
   command that differs from its dev twin (each is re-run on dev first and must
   reproduce the dev predictions byte for byte); and the fact-check matcher
   finding an AVeriTeC claim's own source article (below).

## What runs

**Each test command is its dev twin's command with `--split` changed**, and
before the freeze every one is re-run on dev and must reproduce its dev twin's
predictions file byte for byte (sha256). A test number is then the dev
measurement, moved to unseen data, and nothing else.

**The AVeriTeC verdict is the evidence path, exactly as every dev verdict number
was measured** (164d2289c90b): retrieval `hybrid` (RRF over BM25 depth 200,
k 10), stance `xlmr_nli`, aggregate `learned` (`aggregator_xlmr_nli_prior`, T
0.795 fitted on dev), τ_abstain 0.3835 applied by the harness, the claim taken
as AVeriTeC gives it, and **no fact-check matcher**. Two reasons the full served
pipeline is not what is scored here:

- **The fast path would read the answer.** AVeriTeC claims are taken from
  fact-check articles, and the matcher's pool is 78,077 fact-checks. Run through
  the full served config, the fast path fired on dev claims by matching the
  claim's own source fact-check (dev 00070: a CheckYourFact article on the very
  claim, cosine 0.95). AVeriTeC's rules exclude the source article as evidence;
  here it would be the verdict. The fast path is measured where it is honest,
  on MultiClaim (#12-13).
- **Every dev choice -- aggregator, T, τ, floor -- was made on the evidence
  path.** Scoring a different pipeline on test would test choices nobody made.

Verdict runs use template explanations (the default): the verdict is decided
before any explanation is written. The explainer is measured on its own (#7),
mirroring its dev run (1db244b950ad), which used the NLI stance arm.

| # | Component | Split (n) | Config | Arm, as chosen on dev | Baseline in the same table |
| --- | --- | --- | --- | --- | --- |
| 1 | Verdict, claim-only control | averitec test (307) | `p7_test_verdict_control` | stance `xlmr_claimonly` + `aggregator_xlmr_claimonly`, else served | majority_class |
| 2 | Verdict, served | averitec test (307) | `p7_test_verdict_served` | served | the control (#1), paired bootstrap 2,000 |
| 3 | Verdict, served vs floor | same predictions as #2 | `p7_test_verdict_served_majority` | served | majority_class |
| 4 | Calibration + abstention | same predictions as #2 | (#2's `calibration` block) | ECE; coverage, accuracy, macro-F1 at τ 0.3835 | 100% coverage |
| 5 | Calibration before T | served at T=1 | `p7_test_calibration_served_t1` | served, `--temperature 1.0` | #2's run (ECE after) |
| 6 | Evidence retrieval | averitec test (307) | `p7_test_retrieval_hybrid` / `p7_test_retrieval_bm25` | hybrid RRF@200 | BM25 (its own row, against random_rank) |
| 7 | Explanations | averitec test, retrieved passages, beam | `p7_test_faithfulness_beam` | IndicBART + LoRA, beam | extractive_explanation |
| 8 | Claim span | x_claim test (571) | `p7_test_span_joint` | joint XLM-R | whole_post_span |
| 9 | Claim span, served extractor | x_claim test (571) | `p7_test_span_heuristic` | `claims: heuristic` sentence rule | whole_post_span |
| 10 | Span, romanized (FR-26) | x_claim_romanized test (193) | `p7_test_span_romanized_joint` | joint XLM-R | whole_post_span |
| 11 | Span, native, same posts | x_claim test, the 193 posts' gold | `p7_test_span_native_matched_joint` | joint XLM-R | whole_post_span |
| 12 | Claim matching | multiclaim test (3,156) | `p7_test_match_bge_m3` / `p7_test_match_bm25` | BGE-M3 | random_rank; BM25 in its own row |
| 13 | Fast path | multiclaim test, #12's predictions | `p7_test_fastpath_bge_m3` | cosine gate, τ 0.90 served (τ table 0.55–0.90) | always_match |
| 14 | Normalization | checkthat25_t2 test (1,485) | `p7_test_normalize_extractive` | extractive (span model) | longest_sentence |
| 15 | Language ID | multiclaim test (3,156) | `p7_test_lid_hybrid` | hybrid (script + romanized LID) | majority_class |

Every config breaks down by language and script; MultiClaim's Punjabi cells are
single digits and are reported as fractions with their n.

## Not given a test number, and why

- **Check-worthiness (FR-6).** The derived set ranks arms backwards against
  real forwards (project log, lesson 10), and the 100 hand-typed forwards are
  dev-only and chose the served arm, so any number on them is optimistic.
  Reported as a limitation.
- **Transliteration (FR-5).** Its only gold is the hand-typed set, dev-only by
  design.
- **FR-19 manipulation flags.** No gold exists (SemEval-2023 T3 was never
  obtained); demo-verified.

## Expectations, written before the run

So that a surprising number is questioned rather than celebrated:

- Verdict macro-F1 0.24–0.32 (dev 0.2802; n=307 makes the CI wide). Above ~0.35:
  look for leakage first.
- Test ECE above dev's 0.069 — T was fitted on dev.
- Coverage at τ 0.3835 somewhere near, not exactly at, 60%.
- Span and matching close to dev; romanized Hindi below native, Punjabi near
  parity (dev: −0.034 and +0.007 token F1).
