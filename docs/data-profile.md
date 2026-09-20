# Data profile

_Placeholder. Generated in Session 2 by the profiling script, not written by
hand._

Once the loaders exist, this file records, per dataset:

- rows per split, per language, and per script (native vs romanized)
- label distribution per split, and the majority-class rate — which is the
  dumb baseline any classifier has to beat
- text length distribution
- anything anomalous: duplicates, empty rows, unexpected languages, cells too
  small to support a claim

Run `make status` for a quick live view of whatever is currently in
`data/splits/`.

## Expected counts, from the dataset papers

Recorded here in advance so a loader bug shows up as a mismatch rather than
being quietly accepted.

| Dataset | Split | EN | HI | PA |
| --- | --- | --- | --- | --- |
| X-CLAIM | train | 3891 | 1193 | 346 |
| X-CLAIM | dev | 400 | 100 | 100 |
| X-CLAIM | test | 371 | 100 | 100 |
| CheckThat! 2025 T2 | train | — | 1081 | — |

Punjabi's 346 training examples are the reason any Punjabi result above
English-level performance should be treated as a bug.
