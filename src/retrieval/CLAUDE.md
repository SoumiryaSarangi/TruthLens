# src/retrieval/

Hybrid BM25 + dense retrieval over the evidence corpus. Phase 5 (Unit III).
Empty until then; this file records the conventions so the first commit here
does not have to invent them.

## Model choices, already decided

| Use | Model | Why |
| --- | --- | --- |
| Retrieval | **BGE-M3** | Leads 8 of 13 Indian languages on IndicMSMarco; beat LaBSE on the SemEval-2025 claim-retrieval setting |
| Retrieval fallback | multilingual-E5-large | If BGE-M3 will not fit the compute budget |
| Indic baseline | MuRIL | Gives a three-way embedding comparison rather than one arbitrary pick |
| Lexical baseline | BM25 (`rank_bm25`) | The dumb baseline every dense retriever must beat |

**LaBSE is not a retriever.** It is a translation-ranking model and scored
0.188 average nDCG@10 on BEIR, below every dedicated retrieval model. Its only
role in this project is bitext alignment for the t-SNE cross-lingual plot. If
you find yourself importing LaBSE in this directory, something has gone wrong.

## Conventions

- **Metrics live in `src/eval/`, never here.** This package produces a
  predictions JSONL; it does not score itself.
- Predictions format: `{"uid": ..., "ranked_ids": [...], "scores": [...]}`,
  ranked best-first, at least as deep as the largest `k` in the config.
- Every retriever must be runnable over a fixed candidate pool so its numbers
  are comparable across runs. Note the pool size in the config's `notes:`.
- Retrieval is evaluated **on its own**, before anything touches generation.
  Retrieval metrics and generation metrics never share a table.
- Report Recall@{1,5,10}, MRR and Success@10, split by language **and** by
  script. The harness does the splitting; just make sure `uid`s resolve.

## Baseline discipline

`random_rank` in `src/eval/baselines.py` is the floor. If it scores anywhere
near your retriever, the candidate pool is too small or too filtered — the
harness emits a warning when the pool is under twice the scoring depth, and
that warning is worth taking seriously rather than tuning around.

BM25 is the *real* baseline. A dense retriever that does not beat BM25 on a
language is a finding to report, not a bug to hide — it is exactly the kind of
result the romanization comparison is looking for.

## The thing to measure here

The research contribution is the romanization penalty. For every retrieval
number, the native-script and romanized-script versions of the same claim set
must both be evaluated, and the gap reported. A documented finding already
shows BGE-M3 degrades badly on romanized queries; the open question is *how
much*, and whether it is cheaper to fix here or upstream in transliteration.
