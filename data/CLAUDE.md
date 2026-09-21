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

## Datasets

`make data` fetches everything open-access, rebuilds the splits and reprofiles.
Sources, URLs and the sha256 of every downloaded file live in
`data/raw/DOWNLOADS.json`. Live counts are in `docs/data-profile.md`.

### Acquired

**AVeriTeC** — verification backbone, 5-class verdict
- Repo: https://github.com/MichSchli/AVeriTeC · Homepage: https://fever.ai/dataset/averitec.html
- Paper: Schlichtkrull et al., NeurIPS 2023 Datasets & Benchmarks
- Licence: CC BY-NC 4.0 — **non-commercial, academic use**
- Files: `data/train.json` (3068 claims), `data/dev.json` (500)
- **The real test split is withheld** for the FEVER shared task. We hold out
  10% of the public train, stratified by label with seed 42, as a local test
  set. The official dev split is used unchanged so dev numbers stay comparable
  to published work; our train is correspondingly smaller.
- No per-claim ID upstream. A record's **position in the file is its identity**,
  which is only safe because the file's sha256 is pinned in `DOWNLOADS.json`
  and in the split MANIFEST — a silent re-release changes the hash.
- Label mapping lives in `src/data/labels.py`; the decision is recorded in the
  root `CLAUDE.md`.

**X-CLAIM** — claim span identification, EN/HI/PA
- Repo: https://github.com/mbzuai-nlp/x-claim
- Paper: "Lost in Translation, Found in Spans", EMNLP 2023 main (arXiv 2310.18205)
- Files: `data/{split}-{lang}.csv`, columns `tokens`, `span_start_index`,
  `span_end_index`. `tokens` is a **Python list literal**, not JSON.
- Counts match the paper exactly: EN 3891/400/371, HI 1193/100/100,
  PA 346/100/100. A mismatch here means the loader is wrong.
- Span task, so rows carry **no verdict label**. `label` is optional in the
  split schema for exactly this reason.
- The `en2xx` files are **machine-translated English and are deliberately not
  downloaded**. X-CLAIM's own finding is that joint multilingual training beats
  training on English-translated data; pulling them in by accident would
  undermine the ablation that replicates it.

> **The language column is not the script column.** `train-pa.csv` is 249
> Gurmukhi, 54 Devanagari and 36 Latin rows. `train-hi.csv` has 43 Latin rows.
> Script is detected per row by `src/data/script_id.py` and never inferred from
> the filename. Punjabi is **26.5% non-native script** in train, the largest
> romanized share in the corpus and directly relevant to the contribution.

**AVeriTeC knowledge store** — evidence pool for Phase 1 retrieval
- `make kb` (`scripts/download_knowledge_store.py`). Resumable; safe to
  interrupt and rerun. Downloaded from **`hf.co`, not `huggingface.co`** — the
  long hostname has its TLS sessions reset on this connection (measured 0/12
  success), the short alias works.
- Sizes, measured from the HF API rather than guessed:

  | Split | Size | State |
  | --- | --- | --- |
  | dev | **11.54 GB** | **downloaded** — all Phase 1 needs |
  | train | 63.52 GB (3 files) | not downloaded |
  | test | 40.71 GB | not downloaded, and not wanted |
  | *all* | *115.78 GB* | *does not fit — 112 GB free* |

- **Do not extract it.** The zip is 11.54 GB and expands to **36.55 GB** (x3.2).
  It holds 500 members, `output_dev/{0..499}.json`, **one per dev claim**, so a
  single claim's candidates can be read straight out of the archive with
  `zipfile.ZipFile(...).open(f"output_dev/{idx}.json")`. Extracting all of it
  buys nothing and costs 36 GB.
- Each member is JSONL, one candidate document per line:

  ```json
  {"claim_id": "133", "type": "gold", "query": "...", "url": "https://...",
   "url2text": ["paragraph 1", "paragraph 2", "..."]}
  ```

- **`type` marks provenance, and `type == "gold"` is the annotated evidence** —
  2-4 per claim. That is the retrieval gold for Phase 1's Recall@k, free, with
  no extra annotation. The other ~800-1500 documents per claim (`question`,
  `gpt_url_only`, `most_similar`, `NER`, …) are the distractor pool.
- **The join key is the dev.json index.** Verified end to end: all 500 files
  present for ids 0-499, `claim_id` inside each file agrees with its filename,
  and our split's `source_id` (`averitec:dev.json:133`) parses straight to
  `output_dev/133.json`.
- Retrieval is ranked **within one claim's pool**, which is AVeriTeC's own
  protocol and what makes our numbers comparable to published ones. It is not
  one global corpus — see `../docs/specs/SYSTEM_DESIGN.md` §7 for the separate
  demo-corpus problem.

### Not yet acquired

| Dataset | Role | Status |
| --- | --- | --- |
| MultiClaim / SemEval-2025 T7 | claim matching (Phase 4) | Zenodo record is restricted; **access requested, awaiting approval**. Add a loader and a `SOURCES` entry once the archive is in hand. |
| CheckThat! 2025 Task 2 | claim normalization (Phase 3) | Not started. Requires registration; HI has 1081 train rows. |

### Still open

## Deduplication policy: train yields to eval

Both datasets ship rows that appear in more than one official split. This is
the DS@GT CheckThat! 2025 finding, reproduced: AVeriTeC's official train and
dev share 4 claims and its train holds 71 internal duplicates; X-CLAIM `en`
has 3 train-dev and 2 train-test overlaps.

Two ways to resolve that, one of them honest:

- Drop the row from dev/test — shrinks a published benchmark and makes our
  numbers incomparable with everyone else's. **Rejected.**
- Drop the row from train — costs a few training examples and nothing else.
  **Taken.**

`deduplicate()` in `scripts/build_splits.py` removes from **train** any row
that exactly or near-duplicates a dev/test row, plus within-train duplicates.
Dev and test are never modified, not even to remove duplicates within
themselves; those are counted and reported instead.

A row is dropped as a near-duplicate only when SimHash **and** exact Jaccard
agree (Hamming <= 8 and Jaccard >= 0.80), so a sketch collision cannot
silently shrink the training set.

### Irreducible leakage is allowlisted, not thresholded away

Two X-CLAIM rows appear in both official **dev and test** (Jaccard 0.906 and
0.990). Neither side can be dropped without altering the benchmark, so they
are accepted by exact uid pair in `data/splits/KNOWN_LEAKAGE.json`, each with
a reason. Anything not on that list still fails `make leakage`. This bounds
dev-to-test contamination at 2 of 571 test rows (0.35%), which belongs in the
report rather than a footnote nobody reads.

## Gotchas

- Punjabi has ~346 X-CLAIM training examples. Any Punjabi result above
  English-level performance is a bug, not a breakthrough.
- Romanized input is the primary use case, not an edge case.
