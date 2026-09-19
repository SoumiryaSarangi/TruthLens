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

## Decisions (see full reasoning in docs/build-plan.md)
- Verification backbone: AVeriTeC, not FEVER
- Claim matching: MultiClaim / SemEval-2025 Task 7, no scraping
- Claim span EN/HI/PA: X-CLAIM
- Claim normalization: CheckThat! 2025 Task 2
- Manipulation techniques: SemEval-2023 Task 3 subtask 3 label set
- Retrieval model: BGE-M3 (fallback multilingual-E5-large)