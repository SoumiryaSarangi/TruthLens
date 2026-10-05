# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Derived from `docs/specs/PRD.md` §2 and `docs/specs/UI_UX.md` §1, and from the owner's own statements during the build (not interviewed in this session: the owner asked for PRODUCT.md to be derived from those documents).

- **The recipient of a forward** (the intended end user, and, per the owner, mostly the owner's parents and grandparents): someone who gets a message in a family group and wants to know whether to believe it or pass it on. They type or paste in whatever script is on their keyboard (English, Hindi, Punjabi, very often Roman script), want the answer in their own language, in plain words, and need to see where it comes from. An unexplained verdict from software is just another forward.
- **The evaluator** (the primary audience of this release): a professor, viva panel or interviewer with five minutes who wants to see the system handle realistic input and explain itself.
- **A fact-checker triaging volume** (secondary, not built for in this release).

## Product Purpose

TruthLens checks WhatsApp-style forwarded messages in English, Hindi and Punjabi (native or Roman script). It mirrors how fact-checkers work: first check whether the claim already has a published fact-check, then verify against evidence. Success is that a reader understands the answer in five seconds, can open the sources behind it in one tap, and is told plainly when the system cannot decide. It is a CSE472 (Deep Learning for NLP) student project; its research contribution is measuring the romanization penalty.

## Positioning

A verifier built for the input people actually receive (forwards, mixed languages, Roman-script Hindi and Punjabi) that never gives a verdict without showing evidence, and that treats declining to answer as a first-class, visibly distinct result.

## Operating Context

- Served by FastAPI at `/`; a single static page (`app/static/index.html`, `app.js`, `styles.css`), vanilla JavaScript, no framework, no build step. It calls `POST /verify` and renders the JSON; copy lives in `app/static/i18n/{en,hi,pa}.json`.
- Must work fully offline (system font stack only, no CDN, no web fonts). On Windows, `Nirmala UI` covers Devanagari and Gurmukhi.
- Looks like the chat app the forward came from: a phone-width centred column (max 440 px), chat bubbles, sample chips, a composer. Used live on a projector in a demo, and by relatives on a phone.
- Optional online look-up (Wikipedia, Google Fact Check) only when the reader presses a button, saying exactly what it sends.

## Capabilities and Constraints

- Card states that must all exist: a plain verdict card per checked claim (at most 3), the fast path ("already checked by <publisher>"), a similar-fact-check suggestion, "Be careful", "Hard to say" (abstained, with the system's greyed lean inside Details), not-a-claim (including a greeting, with no "Check it anyway" button), unsupported language, validation errors (422), unavailable (503/504 with Retry), empty and sending ("Checking…") states.
- Honesty rules that are product requirements (`docs/specs/UI_UX.md`, `CLAUDE.md`): colour is never the only signal (every verdict keeps its icon and its word); abstained looks different from NEI (grey, dashed border, "Leaning: ..." line); confidence is a band whose cut points come from `/version` and are never hard-coded; no fake progress bars (the spinner is "Checking…" only); no exclamation marks; plain wording says "probably", never an absolute "true" or "false" for evidence-path results; the browser renders what `/verify` returns and never recomputes it.
- The offline evidence-path guess is never shown as a verdict. A verdict is shown only for a matched published fact-check or a validated live check.
- Accessibility: WCAG AA in light and dark (`prefers-color-scheme`), `aria-live="polite"` on results, a real `<button>` for the evidence expander, `lang="hi"`/`"pa"` on text in those languages, `prefers-reduced-motion` respected.
- Hindi and Punjabi strings were reviewed by a native speaker and are not to be edited in this restyle.

## Brand Commitments

- Name: TruthLens. Tone: calm, plain, honest about uncertainty; the owner explicitly did not want the enlarged type or extra language buttons (15 px base, 440 px column, answers follow the message's script, no language switcher).
- The owner's instruction for the restyle: do NOT use `delight` or `overdrive` (they clash with the calm tone).

## Evidence on Hand

- `docs/specs/UI_UX.md` (screens, states, copy, accessibility, demo script), `docs/specs/PRD.md`, `docs/usability-test.md` (the relatives' test, not yet run).
- Real API responses for every card state: `reports/ui_responses.json` and the Node render checks `scripts/ui_plain_check.js`, `ui_render_check.js`, `ui_live_check.js`, `ui_evidence_check.js`.
- No user research exists yet; the relatives' usability test is pending. No screenshots of the current UI are on file.

## Product Principles

1. No verdict without evidence; abstaining is a feature and must look distinct from "not enough evidence".
2. Legible in five seconds, in the reader's own language and script, with the technical detail one tap away and closed by default.
3. Show the work: every answer opens into its sources.
4. Honest numbers and honest wording over impressive-looking answers.
5. Familiar and calm: it should read like the chat the forward came from, not like a dashboard.

## Accessibility & Inclusion

WCAG AA in light and dark; users reading Devanagari and Gurmukhi (line-height must not clip matras and conjuncts; no negative letter-spacing on those scripts); older readers (plain words, large enough touch targets of at least 2 rem); colour-blind readers (icon and word for every verdict); reduced motion, reduced transparency and increased contrast preferences.
