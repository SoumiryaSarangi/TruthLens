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
- Test:    `make test`
- Lint:    `make lint`
- Leakage: `make leakage`   (run after ANY data change)
- Table:   `make table`     (renders results/*.json into docs/results.md)
- Setup:   `make setup`     (uv provisions Python 3.11; see docs/environment.md)

The harness REFUSES rather than guessing. If `make eval` exits 2, read the
message — it is refusing for one of the reasons in this file. Do not work
around a refusal; a plausible wrong number is worse than no number.

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

- The test split is locked. Evaluating one needs `TRUTHLENS_ALLOW_TEST=1`,
  and that is for the final reported number only, not for model selection.
- Python is 3.11 via uv, NOT the system 3.13. Run through `make`, which sets
  `PYTHONIOENCODING=utf-8` — Windows consoles are cp1252 and crash on
  Devanagari output.

## Where things live
- docs/phase-plan.md        — current phase and what is in scope. Read first.
- docs/environment.md       — interpreter, locks, Windows gotchas
- docs/results.md           — generated results tables (`make table`)
- data/CLAUDE.md            — dataset provenance, split schema, leakage checks
- src/retrieval/CLAUDE.md   — retrieval conventions
- src/eval/evaluate.py      — the only place metrics are computed
- src/eval/baselines.py     — the dumb baselines, which generate predictions
                              through the same path a model does

## Decisions (see full reasoning in docs/build-plan.md)
- Verification backbone: AVeriTeC, not FEVER
- Claim matching: MultiClaim / SemEval-2025 Task 7, no scraping
- Claim span EN/HI/PA: X-CLAIM
- Claim normalization: CheckThat! 2025 Task 2
- Manipulation techniques: SemEval-2023 Task 3 subtask 3 label set
- Retrieval model: BGE-M3 (fallback multilingual-E5-large)

## Open decision, do not guess
AVeriTeC's label set does not match ours. It ships
`Conflicting Evidence/Cherrypicking`, which we have no class for; we have
`NotAClaim`, which AVeriTeC never produces because it comes from the
check-worthiness stage upstream. `src/data/labels.py` raises
`UnresolvedLabelMapping` deliberately rather than picking one. Decide it in
Session 2, write it there, and put it in the report.

## Git
Never add attribution, co-author, or session-link trailers to commit messages.

Commit straight to `main`. No phase branches, no PRs to yourself — this is a
solo repo and a two-week branch is deferred integration, not isolation. CI
runs on every push to `main`, so a break surfaces within a minute either way.

The safety net is commit frequency, not branches: small commits, one logical
change each, committed before starting the next task, so `git reset --hard
HEAD~1` is always a clean escape.

Branch only for work you might genuinely throw away (swapping a retrieval
backbone, a refactor across a whole package). Short-lived — hours, not weeks
— and deleted once merged.