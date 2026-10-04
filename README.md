# TruthLens

Multilingual claim verification for WhatsApp forwards in English, Hindi and Punjabi,
including Hindi and Punjabi typed in Latin letters. CSE472 project (Soumirya Sarangi).

A forward goes in; out come a verdict, the sources behind it, a calibrated confidence, an
explanation, and, when the system is not confident, an explicit refusal to judge. It first looks
for a published fact-check of the same claim (the fast path) and otherwise retrieves evidence and
reasons over it (the evidence path). An optional per-claim button also searches Wikipedia and Google
Fact Check.

## Read this first

- **`docs/report.md`**: the report. Every number carries the results file it came from, and
  `scripts/check_report_numbers.py docs/report.md` verifies them.
- `docs/project-log.md`: the running record of what was built, decided and corrected.
- `docs/acceptance.md`: every requirement, how it was verified, and its status.

## Headline results (and what they do not say)

- On the locked AVeriTeC test split, the served verdict reaches macro-F1 0.2622 against 0.1447
  for always-Refuted, but **does not beat a control that never reads the evidence** (0.3085).
  Retrieval is the limit: only 15% of test claims get a gold document into the top 10.
- Confidence is calibrated out of sample (test ECE 0.039), and abstention ranks claims
  correctly, but its threshold was set too generously.
- Romanizing hurts claim-span detection (Hindi 0.068, Punjabi 0.061 token F1 on identical posts).
- After the test run, a live verdict was added under a **pre-registered rule that was then passed on
  350 fresh claims** (right on 100 of 106 answers, 3 false "Supported" in 225, an answer for only about
  3 claims in 10). A first pre-registered attempt missed its bar by two claims; both are reported.
  Validated on FEVER-style claims, not on real forwards.

## Run it

Python 3.11 via uv (not the system Python); see `docs/environment.md` for the GPU and Windows notes.

```
make setup            # environment (uv provisions Python 3.11)
make test             # the test suite (many ML tests skip without the models)
make lint
make leakage          # after ANY data change
make eval CONFIG=configs/<name>.yaml     # any number in the report; writes results/<hash>.json
make table            # renders results/*.json into docs/results.md
```

The demo, on a machine with the models and data:

```
python scripts/demo_check.py             # must print OK before presenting
.venv\Scripts\python.exe scripts\serve.py    # or: make serve   (http://127.0.0.1:8000)
```

The server is ready after about a minute; the live-search models load in the background about 40 seconds
later. The live button needs the network and a Google Fact Check key in a git-ignored `.env`
(`.env.example`); never commit the key.

## Layout

| Path | What |
| --- | --- |
| `src/` | the pipeline stages (preprocess, claims, matching, retrieval, stance, aggregation, generation, faithfulness, manipulation, live), the harness (`src/eval/`) |
| `app/` | the FastAPI server and the single-page UI (`app/static/`, strings in `i18n/{en,hi,pa}.json`) |
| `configs/` | one YAML per experiment, and the served pipeline `configs/pipeline/dev.yaml` |
| `data/splits/` | the frozen splits (never regenerated); raw text stays local and gitignored |
| `docs/` | report, specs (`docs/specs/`), protocols, acceptance matrix, error analysis |
| `scripts/` | measurement, plotting, demo and live-verdict tooling |
| `results/` | every experiment's results file, named by its config hash |

## Rules the project keeps

Frozen splits are never regenerated; the test split was run once (`docs/test-protocol.md`) and
nothing after it may change a reported number; no metric is computed outside `src/eval/evaluate.py`;
every model is compared with a dumb baseline in the same table; decisions are taken by a rule written
before the run and validated on fresh data.

## Data and licences

AVeriTeC, MultiClaim (access-restricted, not redistributed), X-CLAIM, CheckThat! 2025 Task 2,
Dakshina and FEVER (CC BY-SA) are used under their own licences; see `data/CLAUDE.md` and
`docs/report.md` section 10. Raw dataset text is never committed. Wikipedia text shown in the live
card is available under CC BY-SA 4.0 and keeps its link.
