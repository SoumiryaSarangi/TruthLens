# Changelog

All notable changes to TruthLens. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/). The fine-grained, dated record of every decision (including the
ones that failed) is [`docs/project-log.md`](docs/project-log.md); this file is the release-level summary.

Entries marked **post hoc** were decided after seeing numbers and are not validated by a pre-registered rule.

## [Unreleased]

### Added
- `docs/MESSAGING.md`: a researched plan for connecting WhatsApp (Meta Cloud API), with Twilio sandbox and Telegram fallbacks, for a VM or a GPU machine plus tunnel. Not built.
- `requirements/README.md`.
- `docs/DEPLOYMENT.md`, and `scripts/package_runtime.py` to pack the git-ignored runtime data (2.1 GB) for a deployment.
- `TRUTHLENS_HOST` and `PORT` for `scripts/serve.py`, and a `TRUTHLENS_GIT_SHA` fallback for `/version` when there is no `.git`.

### Changed
- The Python lock files moved from the repository root into `requirements/` as `core`, `dev` and `ml` (contents and hashes unchanged; Makefile, CI and docs updated).
- README: how to start the server without `make` (Windows PowerShell commands) and how to install without `make`.

### Fixed
- CI: the icon and cache-header tests no longer require Pillow or FastAPI, which the slim CI lock does not install.

## [1.0.0] - 2026-10-12

First complete release.

### Added
- **Responsive proof-desk UI** at every width (phone band-desk-dock, tablet and laptop two panes, wide two-column desk),
  light and dark, offline, reduced-motion safe, with a living shader gradient on the rail over an always-present CSS
  gradient, a legibility scrim and a frame-rate throttle (`ui-src/`, `app/static/vendor/rail-shader.js`).
- Favicon (SVG, ICO), Apple touch icon, web manifest and theme colour.
- **Live fact-check match threshold 0.70**, chosen by a pre-registered rule (served confirmation: 56 shown, 51 of 52
  decidable right, 0 false "Supported" in 205; run `f0d7ab316ff0`).
- **Polarity guard** on fact-check matches (translate a Hindi/Punjabi matched claim, then an NLI contradiction check).
  Served on an owner decision after it narrowly missed its pre-registered rule; **post hoc**, with a threshold of 0.9 and a
  first-sentence premise refinement added after false blocks (run `b3a6fdfb6933`).
- "Which words mattered" word view for live verdicts (shipped under a faithfulness rule fixed in advance; run `4095b565e764`).
- Documentation set: model card, API reference, architecture, operations runbook, security policy, contributing guide,
  third-party notices, citation file, issue and pull-request templates.

### Changed
- The page is one responsive design; the WhatsApp-styled phone column was retired, so narrowing a window no longer
  changes the look.
- The server sends `Cache-Control: no-cache` for the page and its files, and asset links are versioned, so a browser
  never keeps an old design after an upgrade.
- The first answer on a laptop clears the corner "What this is for" link; its popover now opens from its own corner.
- The design system (`DESIGN.md`) documents the full type ramp and radii; the design detector reports no findings.

### Fixed
- A fact-check match was silenced by the guard when the matched claim ended in a question or differed in a number
  (for example "500 times" against "500%"). **post hoc**
- The copy confirmation is announced to screen readers.

### Measured and not shipped
Each was pre-registered with its pass rule and failed it; the code is kept behind a flag or unwired.
- Better Wikipedia queries (entity and acronym search): pooled ratio 0.92 against 1.25 needed (run `b2a05007981d`).
- A hoax-cue rule for "be careful" (`docs/careful-rule-protocol.md`).
- A fact-check "why" reader, two takes (45% and 60% against a 70% bar).
- Translation route variants for romanized claims: both worse than the served route (run `366771a6687f`).

### Known issues
- The live check is silent on most real, local forwards (about 96% of 150 owner-written claims).
- Negated claims reaching the Wikipedia evidence path can be misread as refuted.
- Romanized-Punjabi translation is poor; a better translator does not fit a 6 GB GPU.
- No usability study with the intended readers has been run.

## [0.9.0] - 2026-10-05

### Added
- Real-claims measurement of the live check (AVeriTeC dev 500 and owner-written sets), with the silence diagnosis
  (`docs/real-claims-protocol.md`, `docs/silence-diagnosis-protocol.md`).
- Desktop "proof desk" workspace and the design records (`PRODUCT.md`, `DESIGN.md`, `.impeccable/`).
- "Built for / Not built for" statement, plain verdict cards, the greeting gate, "sources disagree" wording.

## [0.8.0] - 2026-10-02 to 2026-10-04

### Added
- **Live look-up** (Wikipedia and Google Fact Check, opt-in per claim) with a verdict only under the pre-registered
  two-NLI-model agreement rule, validated on 350 fresh claims (right on 100 of 106, 3 false "Supported" in 225).
- Lexicon-first transliteration and a native-script query for romanized free text.
- The test split was run **once** (`docs/test-protocol.md`): all 15 pre-registered components, on frozen code.

## [0.1.0] - 2026-09-20 to 2026-10-02

### Added
- Frozen splits for AVeriTeC, X-CLAIM, MultiClaim and CheckThat! 2025; leakage checks; the evaluation harness with
  per-language and per-script metrics and mandatory baselines.
- The pipeline: language and script ID, transliteration, check-worthiness, claim matching (BGE-M3), hybrid retrieval,
  NLI stance, calibrated aggregation with abstention, generation and a faithfulness gate.
- The romanization-penalty measurement.
