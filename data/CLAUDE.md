# data/

## The one rule

`data/splits/` is **frozen**. Never regenerate it. If a split file looks
wrong, stop and ask — do not fix it by rebuilding it. Every number in
`results/` is tied to the exact bytes of the split it was computed against.

Enforced in four places, so no single mistake gets through:

1. `data/splits/SPLITS.lock` — sha256 and line count of every split file
2. `tests/test_splits_frozen.py` — recomputes them, runs in CI
3. `scripts/build_splits.py` — refuses to overwrite without three separate confirmations
4. `.claude/settings.json` — denies `Write`/`Edit` under `data/splits/**`

## Layout

| Path | Committed? | What it is |
| --- | --- | --- |
| `data/raw/` | no (gitignored) | Downloaded datasets, exactly as they arrived |
| `data/interim/` | no (gitignored) | Materialised text keyed by `uid`, rebuilt by `make data` |
| `data/gold/` | no (gitignored) | Task-specific gold files, e.g. `uid -> relevant_ids` |
| `data/splits/` | **yes, frozen** | ID manifests — the definition of train/dev/test |

## Split record schema

A split file is an **ID manifest, not text**. It carries identifiers and
hashes, never the claim itself. That is what lets the repo be public without
redistributing AVeriTeC, X-CLAIM or the access-restricted MultiClaim corpus —
which the build plan commits to under "Things deliberately not being done".

One JSON object per line, keys sorted, LF endings:

```json
{"uid":"xclaim:hi:train:0042","dataset":"x_claim","split":"train","lang":"hi",
 "script":"deva","source_id":"1483...","label":"claim","label_set":"span_bio",
 "text_sha1":"9f2a...","simhash64":"f399500c3021c68e","n_chars":137}
```

| Field | Notes |
| --- | --- |
| `uid` | The join key. Every predictions file and every metric keys off this. |
| `lang` | `en` / `hi` / `pa` |
| `script` | `deva` / `guru` / `latn`. Present from day one — per-script reporting is the research contribution, not an afterthought. |
| `source_id` | The upstream record id. Catches a row re-keyed under a new `uid`. |
| `text_sha1` | SHA-1 of the **normalised** text. Detects exact duplicates across splits. |
| `simhash64` | 64-bit SimHash over char 5-grams. Detects near-duplicates without shipping text. |
| `label` | Optional; absent for retrieval-only splits. |

The schema is enforced by `src/data/splits.py:validate_split_record`. An
unexpected field is an error, not a warning — a field present in one dataset's
splits and absent from another's is how per-language breakdowns start
disagreeing with each other.

## Normalisation: read this before using it

`src/data/normalize.py:normalize_for_hashing` is for **deduplication and
leakage detection only**. It strips zero-width joiners, which carry real
orthographic meaning in Devanagari and Gurmukhi, casefolds, and deletes emoji.

Never feed its output to a model. Model-facing preprocessing is a separate
function and arrives in Phase 2 under `src/preprocess/`.

## Leakage

`make leakage` after **any** data change. Four checks, all runnable from the
committed manifests with no source text:

| Check | Catches |
| --- | --- |
| `uid` overlap | the same row in two splits |
| `source_id` overlap | the same upstream record re-keyed |
| `text_sha1` overlap | identical normalised text under a different id |
| SimHash proximity | near-duplicates: punctuation, casing, added forward headers |

**Known limitation, stated plainly:** this catches duplicates and trivial
variants, not semantic paraphrase. Two sentences that mean the same thing in
different words score around 9–11 Hamming, overlapping the warning band, and a
genuinely reworded claim can be missed. Embedding-based duplicate detection
belongs in Phase 4 alongside the claim-matching retriever. Until then,
`make leakage` passing means *no duplicates*, not *no overlap*.

This matters because it is not hypothetical: the DS@GT team on CheckThat! 2025
found substantial claim overlap, to the point of duplication, across train,
dev and test in this exact family of data.

## Datasets (download instructions land in Session 2)

| Dataset | Role | Access |
| --- | --- | --- |
| AVeriTeC | verification backbone, 4-class verdict | TBD |
| X-CLAIM | claim span, EN/HI/PA | EN 3891/400/371, HI 1193/100/100, PA 346/100/100 |
| CheckThat! 2025 Task 2 | claim normalization | HI has 1081 train |
| MultiClaim / SemEval-2025 T7 | claim matching | Zenodo record is **restricted — request access early** |

Two open items carried from `docs/build-plan.md`:

- **AVeriTeC knowledge store size.** ~1000 articles across 4568 claims is
  large. There are ~109 GB free on this machine, so plan on a subset and check
  before downloading.
- **The AVeriTeC label mismatch.** AVeriTeC ships
  `Conflicting Evidence/Cherrypicking`; the project's scheme has no such class
  and adds `NotAClaim`, which AVeriTeC never produces. `src/data/labels.py`
  raises `UnresolvedLabelMapping` rather than guessing. Decide it and record
  the decision there and in the report.

## Gotchas

- Punjabi has ~346 X-CLAIM training examples. Any Punjabi result above
  English-level performance is a bug, not a breakthrough.
- Romanized input is the primary use case, not an edge case.
