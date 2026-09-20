# Current phase and what is in scope

Pointer file. The reasoning lives in [build-plan.md](build-plan.md); this says
only where the project is right now, so a session can be oriented in ten
seconds without reading the whole plan.

**Update the "Current phase" line at the start of every session.**

## Current phase

**Phase 0 — harness before models.** Complete.

In scope: repo skeleton, pinned dependencies, the frozen-splits convention,
the eval harness, the leakage test, CI.

Out of scope, deliberately: **all model code**. Nothing in `src/` imports
torch, transformers, sentence-transformers or FAISS yet.

## What exists

| Piece | Where | State |
| --- | --- | --- |
| Eval harness | `src/eval/evaluate.py` | Works: classification + retrieval |
| Metrics | `src/eval/metrics.py` | Cross-checked against scikit-learn |
| Dumb baselines | `src/eval/baselines.py` | majority_class, stratified_random, random_rank |
| Leakage detection | `src/data/leakage.py` | 4 checks, proven against planted leaks |
| Frozen splits | `data/splits/` | Convention + lock in place; **no data yet** |
| Dataset loaders | `src/data/` | Not started — Session 2 |

## Next: Session 2 — data

Write `src/data/` loaders for AVeriTeC, X-CLAIM and CheckThat! 2025 Task 2.
For each: download instructions in `data/CLAUDE.md`, a loader returning the
common schema, and a profiling script reporting per-language and per-split
counts into `docs/data-profile.md`. Then build the frozen splits and make
`make leakage` pass on real data. Do not touch models.

Two decisions are blocking and must be made during that session, not after:

- **The AVeriTeC label mapping.** `src/data/labels.py` raises
  `UnresolvedLabelMapping` for `Conflicting Evidence/Cherrypicking` on
  purpose. Pick one of the three options documented there and record why.
- **AVeriTeC knowledge store size.** ~109 GB free on this machine. Check
  before downloading; a subset is likely necessary.

## Phase order

| Phase | Weeks | What |
| --- | --- | --- |
| 0 | — | Harness. **Done.** |
| 1 | 1–2 | Vertical slice, English only |
| 2 | 3–4 | Language layer; the native vs romanized table |
| 3 | 5 | Front of pipeline: check-worthiness, span ID, normalization |
| 4 | 6–7 | Claim matching |
| 5 | 8–9 | Evidence retrieval and stance |
| 6 | 10–11 | Verdict aggregation and grounded generation |
| 7 | 12–13 | Demo, ablations, report. **Code freezes end of week 12.** |

## The cut list, in order

Decided in advance so it is not decided in panic at week 11.

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
