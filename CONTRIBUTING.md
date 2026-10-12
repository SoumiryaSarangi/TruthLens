# Contributing to TruthLens

Thank you for considering a contribution. TruthLens is a measured research system more than a product, so the rules about
*how* a change is made matter as much as the code. Please read this before opening a pull request.

## Ground rules

These are non-negotiable; [`CLAUDE.md`](CLAUDE.md) states them for the maintainer's tooling, and the tests enforce several.

1. **Never regenerate `data/splits/`.** The splits are frozen and committed. If one looks wrong, open an issue.
2. **The test split is spent.** It was run once (`docs/test-protocol.md`). Nothing after that may change a reported number,
   and the test flag is not for model selection.
3. **Every experiment writes `results/<config-hash>.json`**, with seed 42 set in numpy, torch, random and transformers.
4. **No metric is computed outside `src/eval/evaluate.py`.** Never inline in a notebook or a script.
5. **Every model sits beside the dumb baseline** in the same table. A model without a baseline is not a result.
6. **Pre-register decisions.** Write the rule and its pass bar *before* you run, commit it, then run once. Anything you
   decide after seeing numbers is labelled **post hoc**. A failed attempt is reported, not hidden.
7. **Do not change the frozen live rule (V2)** (two NLI models must agree, English route) without a new protocol on
   fresh claims.
8. **Secrets stay out.** The Google Fact Check key is in a git-ignored `.env`. Never print, log, paste or commit it.
9. **Private data stays private.** `data/private/` is git-ignored; owner-written claim files are *written* claims and must
   never be described as collected forwards.

## Setting up

```bash
make setup            # uv provisions Python 3.11, installs the hash-pinned locks, wires pre-commit
make setup-ml         # the ML stack, if you will run the models
make lint && make test
```

Python is **3.11** (not the system 3.13). On Windows, run through `make` (it sets `PYTHONIOENCODING=utf-8`) or set it
yourself, or Devanagari output will crash the console. See [`docs/environment.md`](docs/environment.md).

Stop the server before running GPU scripts or `tests/test_orchestrator.py`: two GPU processes do not fit
([`docs/OPERATIONS.md`](docs/OPERATIONS.md)).

## Making a change

1. **Open an issue first** for anything beyond a typo or a small fix, so the approach can be agreed.
2. **Branch** from `main` for work you might throw away; keep it short-lived.
3. **Keep commits small and single-purpose**, one logical change each, with a message that says what and why.
   Do not add attribution or co-author trailers.
4. **Add or update tests.** A bug fix gets a test that fails before the fix.
5. **Run** `make lint`, `make test`, and `make leakage` after any data change. CI runs the same plus the frozen-split guards.
6. **Update the docs** that describe what you changed: the relevant spec, `docs/project-log.md` for decisions, and
   `CHANGELOG.md` under *Unreleased*.
7. **Open a pull request** using the template. Say what you measured, against what baseline, and what you did *not* test.

## Code style

- Python 3.11, formatted and linted by `ruff` (line length 100, rules in `pyproject.toml`).
- Match the surrounding code's naming, comment density and idiom.
- Stages are typed functions of the shape in `docs/specs/SYSTEM_DESIGN.md`; a stage reads only earlier stages' fields.
- Imports of heavy libraries are lazy; `tests/test_contracts.py` fails the build if `src/` imports torch at module scope.

## Front end

- The page is vanilla JS and CSS: **no framework, no CDN, no web fonts, system fonts only, it must work offline.**
- Design decisions follow [`PRODUCT.md`](PRODUCT.md) and [`DESIGN.md`](DESIGN.md): colour is never the only signal, abstained
  must look different from "not enough evidence", no fake progress, no exclamation marks, AA contrast in light and dark,
  `prefers-reduced-motion` respected.
- A new text/background colour pair is a token, defined in light and dark, and added to `tests/test_ui_static.py`.
- Hindi and Punjabi strings were reviewed by a native speaker; do not edit them without a reviewer.
- The only built file is `app/static/vendor/rail-shader.js`; rebuild it with `npm run build:rail` when `ui-src/` changes.

## Reporting bugs and wrong answers

Use the issue templates. For a **wrong verdict**, include the exact text, the answer you got, what you expected, and the
source that settles it. Do not include private messages from other people.

## Licence

By contributing you agree your contribution is licensed under the [MIT licence](LICENSE).
