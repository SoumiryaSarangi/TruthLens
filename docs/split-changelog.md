# Split changelog

Every regeneration of a frozen split, and why.

**An entry here means every `results/*.json` produced before it against the
same split is no longer comparable.** That is the cost, and it is why
`scripts/build_splits.py` requires three separate confirmations before it will
overwrite anything.

Entries are appended automatically by `scripts/build_splits.py` when a rewrite
is forced. Do not add one by hand without actually rewriting a split.

## Before adding an entry

Answer this first: is the split wrong, or is the code reading it wrong? It is
almost always the second. CLAUDE.md: "If a split file seems wrong, stop and
ask."

---

_No splits have been regenerated. The first frozen splits are built in
Session 2._

## 2026-09-23T20:21:58+00:00 — data/splits/x_claim/dev.jsonl

Cross-dataset leakage. CheckThat! 2025 Task 2 shares a post pool with X-CLAIM: 775 x_claim/train rows are in CheckThat dev/test and 105 are in MultiClaim dev/test. 'Train yields to eval' was only applied WITHIN a dataset; it is now applied across all of them. Only x_claim/train changes -- dev and test are untouched, so X-CLAIM numbers stay comparable with the published benchmark. No results JSON was computed against x_claim, so nothing is invalidated, but the romanized language-ID classifier trains on it and is retrained and re-measured in the same commit.

## 2026-09-23T20:21:58+00:00 — data/splits/x_claim/test.jsonl

Cross-dataset leakage. CheckThat! 2025 Task 2 shares a post pool with X-CLAIM: 775 x_claim/train rows are in CheckThat dev/test and 105 are in MultiClaim dev/test. 'Train yields to eval' was only applied WITHIN a dataset; it is now applied across all of them. Only x_claim/train changes -- dev and test are untouched, so X-CLAIM numbers stay comparable with the published benchmark. No results JSON was computed against x_claim, so nothing is invalidated, but the romanized language-ID classifier trains on it and is retrained and re-measured in the same commit.

## 2026-09-23T20:21:58+00:00 — data/splits/x_claim/train.jsonl

Cross-dataset leakage. CheckThat! 2025 Task 2 shares a post pool with X-CLAIM: 775 x_claim/train rows are in CheckThat dev/test and 105 are in MultiClaim dev/test. 'Train yields to eval' was only applied WITHIN a dataset; it is now applied across all of them. Only x_claim/train changes -- dev and test are untouched, so X-CLAIM numbers stay comparable with the published benchmark. No results JSON was computed against x_claim, so nothing is invalidated, but the romanized language-ID classifier trains on it and is retrained and re-measured in the same commit.

## 2026-09-23T20:26:24+00:00 — data/splits/multiclaim/dev.jsonl

Cross-dataset leakage, same pass as x_claim. 95 multiclaim/train rows are in CheckThat! 2025 Task 2's dev/test and 72 are in X-CLAIM's. Only multiclaim/train changes; dev and test are untouched, so every retrieval number already reported against multiclaim/dev stands. The in-domain Word2Vec rung of the embedding ladder trains on multiclaim/train, so it is retrained and re-scored in the same commit.

## 2026-09-23T20:26:26+00:00 — data/splits/multiclaim/test.jsonl

Cross-dataset leakage, same pass as x_claim. 95 multiclaim/train rows are in CheckThat! 2025 Task 2's dev/test and 72 are in X-CLAIM's. Only multiclaim/train changes; dev and test are untouched, so every retrieval number already reported against multiclaim/dev stands. The in-domain Word2Vec rung of the embedding ladder trains on multiclaim/train, so it is retrained and re-scored in the same commit.

## 2026-09-23T20:26:28+00:00 — data/splits/multiclaim/train.jsonl

Cross-dataset leakage, same pass as x_claim. 95 multiclaim/train rows are in CheckThat! 2025 Task 2's dev/test and 72 are in X-CLAIM's. Only multiclaim/train changes; dev and test are untouched, so every retrieval number already reported against multiclaim/dev stands. The in-domain Word2Vec rung of the embedding ladder trains on multiclaim/train, so it is retrained and re-scored in the same commit.

## 2026-09-24 — correction to the two entries above

`data/splits/multiclaim/dev.jsonl` and `data/splits/multiclaim/test.jsonl` did
**not** change. Verified against git: only the `train.jsonl` files differ from
the previous commit; every dev and test split is byte-identical. The same
applies to the x_claim entry, which names dev and test in its reason text but
only moved train.

The spurious entries came from `freeze_split` logging any write to an existing
tracked file, and rebuilding a dataset re-freezes all of its splits. That made
the log say prior results were no longer comparable when they were. Fixed in
`scripts/build_splits.py`: a write whose bytes are identical is no longer
recorded as a change. Entries are left in place rather than deleted, because an
append-only log that gets edited is not an audit trail.

**No results/*.json produced before those entries is invalidated.**

## 2026-09-23T21:42:52+00:00 — data/splits/x_claim/train.jsonl

Cross-dataset dedup is now EXACT-MATCH only. Confirming a near-duplicate needs text on both sides, and a committed split carries ids and hashes, not text -- so using near-duplicates across datasets made x_claim/train's content depend on MultiClaim's restricted text. The same build produced 4398 rows locally and 4446 on the CI runner. A public split has to be rebuildable from public data, so the ~48 cross-dataset near-duplicates are now REPORTED rather than dropped. Exact match still catches 884 of the 932 leaking rows, and near-duplicate detection within each dataset is unchanged.

## 2026-09-23T21:43:51+00:00 — data/splits/checkthat25_t2/train.jsonl

Cross-dataset dedup is now EXACT-MATCH only. Confirming a near-duplicate needs text on both sides, and a committed split carries ids and hashes, not text -- so using near-duplicates across datasets made x_claim/train's content depend on MultiClaim's restricted text. The same build produced 4398 rows locally and 4446 on the CI runner. A public split has to be rebuildable from public data, so the ~48 cross-dataset near-duplicates are now REPORTED rather than dropped. Exact match still catches 884 of the 932 leaking rows, and near-duplicate detection within each dataset is unchanged.

## 2026-09-23T22:09:56+00:00 — data/splits/multiclaim/train.jsonl

Rebuilt under the exact-match cross-dataset rule, the same change applied to x_claim and checkthat25_t2. multiclaim/train had been built while cross-dataset dedup still used near-duplicate matching, so it no longer reproduced from source. Only train changes; dev and test are untouched.
