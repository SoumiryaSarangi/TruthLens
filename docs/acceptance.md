# Acceptance matrix (SRS §7)

**Written for:** whoever signs off the release, and the viva.

SRS §7: the release is accepted when every P0 requirement is verified by its
stated method, every cut P1/P2 is recorded with its reason, and `make test`,
`make lint` and `make leakage` pass on a clean clone. One row per requirement;
the evidence column names a test, a results hash (`results/<hash>.json`), a
script or a demo step — something that can be re-run, not a claim.

Status: **V** verified · **V\*** verified with a stated limitation · **CUT** cut,
with the reason.

## Functional requirements

| ID | Pri | Method | Evidence | Status |
| --- | --- | --- | --- | --- |
| FR-1 | P0 | test | `tests/test_api.py::test_verify_rejects_empty_text`, `::test_verify_rejects_overlong_text`; UI shows 422 inline (`tests/test_ui_static.py`, demo) | V |
| FR-2 | P0 | test | `tests/test_stage_preprocess.py` | V |
| FR-3 | P0 | test, eval | `tests/test_stage_lid.py`; MultiClaim dev 7f4d2e1ee058; test `p7_test_lid_hybrid` | V |
| FR-4 | P0 | test | `tests/test_stage_preprocess.py`, `src/data/script_id.py` tests | V |
| FR-5 | P0 | test, eval | `tests/test_stage_translit.py`; hand-typed dev f141a4d92b33 (rule-based CER 0.4281, identity 0.8518) | V\* — rule-based; IndicXlit ruled out (would replace CUDA torch) |
| FR-6 | P0 | test, eval | `tests/test_stage_claims.py`; hand-typed dev e9487da211c6 (served heuristic) | V\* — no test number (`docs/test-protocol.md`) |
| FR-7 | P0 | test, eval | `tests/test_claims_heuristic_span.py`; X-CLAIM dev f599f727f473; test `p7_test_span_*`; CheckThat test `p7_test_normalize_extractive` | V |
| FR-8 | P0 | eval | MultiClaim dev da5132cee8a0; test `p7_test_fastpath_bge_m3`; demo chip 1 | V\* — fires on ~2% of posts at τ 0.90 |
| FR-9 | P0 | eval | AVeriTeC dev d153f28ff603 (hybrid) vs cb8f6f0f3b5c (BM25); test `p7_test_retrieval_*` | V |
| FR-10 | P0 | eval | `configs/p5_stance_*` (derived dev) | V |
| FR-11 | P0 | eval | dev 164d2289c90b; learned vs rule, Phase 6; test `p7_test_verdict_*` | V |
| FR-12 | P0 | test | `tests/test_orchestrator.py::test_empty_pool_gives_nei_and_abstains`, `::test_nothing_above_the_relevance_floor_is_nei_abstained_with_its_passages` | V |
| FR-13 | P0 | eval | dev ECE 0.0988 → 0.0690 (204b09b37d27 → 164d2289c90b); test `p7_test_calibration_served_t1` → `p7_test_verdict_served` | V |
| FR-14 | P0 | eval, test | τ 0.3835 chosen on dev (164d2289c90b); `tests/test_orchestrator.py::test_abstention_threshold_is_applied`; test at fixed τ (`calibration.tau`) | V |
| FR-15 | P0 | eval, demo | dev 1db244b950ad (faithful 0.524); test `p7_test_faithfulness_beam` | V |
| FR-16 | P0 | test, eval | `tests/test_generation_gate.py`, `tests/test_stage_faithfulness.py` | V |
| FR-17 | P1 | demo | explanations are English; the card says so for hi/pa input | CUT — cut-list item 3 (Punjabi generation), extended to Hindi: the explainer is trained on English AVeriTeC justifications |
| FR-18 | P0 | test | `tests/test_generation_gate.py` (gate failure, generation error, timeout); `tests/test_orchestrator.py::test_abstention_threshold_is_applied` (abstained) | V |
| FR-19 | P2 | demo | `tests/test_manipulation.py`; demo chip 4 | V\* — unmeasured, no SemEval gold |
| FR-20 | P0 | test | `tests/test_api.py::test_verify_returns_the_documented_shape` | V |
| FR-21 | P0 | test | `tests/test_api.py::test_health_reports_each_stage`, `::test_version_reports_taus_and_confidence_bands` | V |
| FR-22 | P0 | test | `tests/test_orchestrator.py::test_trace_records_every_stage_it_ran` | V |
| FR-23 | P0 | demo | `app/static/`; `scripts/demo_check.py` exit 0; demo order 5, 1, 2, 6 | V\* — hi/pa strings await native review |
| FR-24 | P0 | test | `tests/test_batch.py` (batch output scores through the real harness) | V |
| FR-25 | P0 | review | `docs/results.md`: every row carries its baseline | V |
| FR-26 | P0 | review, eval | hand-typed 100 (`data/splits/handtyped/`); MultiClaim natural romanized; `x_claim_romanized` dev 02c59ee296a0 / f05dd5f44b16, test `p7_test_span_romanized_joint` | V |
| FR-27 | P1 | review | `docs/figures/tsne_parallel_claims.png` | V |

## Non-functional requirements

| ID | Method | Evidence | Status |
| --- | --- | --- | --- |
| NFR-1 | test (timed) | `scripts/measure_latency.py` → `docs/environment.md` | pending |
| NFR-2 | review | same | pending |
| NFR-3 | review | same; Phase 6: 3.56 GiB peak | pending |
| NFR-4 | review | `docs/environment.md`: one GPU job at a time | V |
| NFR-5 | test | `tests/test_provenance.py`; every result carries config hash, git SHA, env | V |
| NFR-6 | test | `make leakage`; test lock in `evaluate.py`, `pipeline/batch.py`, `score_passages.py` (`common/test_guard.py`) | V |
| NFR-7 | test | `tests/test_orchestrator.py` degradation tests; `tests/test_manipulation.py::test_a_failing_flagger_degrades_to_no_flags` | V |
| NFR-8 | review | no request logging in `app/main.py`; no network calls in the pipeline | V |
| NFR-9 | eval, demo | NotAClaim on opinions/greetings (demo chip 5); every verdict card shows sources | V |
| NFR-10 | test | CI green on the final commit | pending |
| NFR-11 | test | CI on Linux, local on Windows; `PYTHONIOENCODING=utf-8` in `make` | V |
| NFR-12 | review | `tests/test_ui_static.py` (WCAG AA, light and dark); keyboard walk-through | V |

## Clean clone

`git clone` into a fresh directory, then `make test`, `make lint`, `make leakage`
there: *(recorded after the code freeze)*.
