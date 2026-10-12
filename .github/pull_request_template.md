## What and why

<!-- One or two sentences. Link the issue. -->

## How it was checked

- [ ] `make lint` and `make test` pass
- [ ] `make leakage` run, if data changed
- [ ] A test fails without this change and passes with it
- [ ] Docs updated (spec, `docs/project-log.md`, `CHANGELOG.md` under *Unreleased*)

## Measurement (if this changes behaviour)

- Rule and pass bar, written **before** the run (link the protocol):
- Result, against the baseline, with its results file:
- Decided after seeing numbers? If yes, it is labelled **post hoc**:

## Rules check

- [ ] No frozen split regenerated; the test flag not used
- [ ] No secret, private data or raw dataset text added
- [ ] Front end stays vanilla and offline (if touched); new colour pairs are tokens with tests

## What was not tested
