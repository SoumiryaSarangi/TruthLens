# TruthLens — UI / UX Specification

| | |
| --- | --- |
| **Status** | v1.0 · 21 Sep 2026 |
| **Owns** | Screens, states, visual language, copy, accessibility, demo script |
| **Does not own** | Response fields → `SYSTEM_DESIGN.md` §8 (this document only maps them to the screen) |
| **Built** | Plain functional page in Phase 1; full styling in Phase 7 |

---

## 1. Design goals

1. **Legible in five seconds.** A judge who has never seen the project understands the verdict before reading a word of explanation.
2. **Honest about uncertainty.** Confidence and abstention are as visible as the verdict itself.
3. **Familiar.** It looks like the chat app the forward came from, so the scenario explains itself without a slide.
4. **Show the work.** One tap from any verdict to the sources behind it.

## 2. Technology

A single static page — `app/static/index.html`, `app.js`, `styles.css` — served by FastAPI at `/`. Vanilla JavaScript, no framework, no build step. It calls `POST /verify` and renders the JSON. Copy strings live in `app/static/i18n/{en,hi,pa}.json`.

Fonts: system stack only, no web fonts, because the demo must work offline. On Windows, `Nirmala UI` covers Devanagari and Gurmukhi; fall back to `Noto Sans Devanagari`, `Noto Sans Gurmukhi`, then `sans-serif`.

## 3. Layout

```
┌──────────────────────────────────────┐
│  ◉ TruthLens        ● models ready   │  header, health dot from /health
├──────────────────────────────────────┤
│                                      │
│  ┌ how it works, one line ┐          │  empty state only
│                                      │
│          ┌────────────────────────┐  │
│          │ ↪ Forwarded            │  │  user bubble, right
│          │ ye sach hai kya ki ... │  │
│          └────────────────────────┘  │
│  ┌──────────────────────────────┐    │
│  │  VERDICT CARD                │    │  system reply, left
│  └──────────────────────────────┘    │
│                                      │
├──────────────────────────────────────┤
│ [EN claim] [हिंदी] [Roman Hindi] [ਪੰਜਾਬੀ]  │  sample chips
│ ┌──────────────────────────────┐ ➤  │  composer
└──────────────────────────────────────┘
```

Layout (amended 2026-10-12): one responsive proof desk from a phone to a wide laptop; see "The responsive proof desk" below. The centred 440 px phone column of the original design is retired.

**Sample chips** fill the composer with a canned forward, one per path in §11. They exist so a live demo never depends on typing Hindi on a projector keyboard.

### The responsive proof desk (2026-10-05 desktop; 2026-10-12 every width; owner's requests)

The page is a **proof desk** at every width, never a phone column floated in a browser and never a different look when a window is made smaller. Layout, tokens and rules are all in `styles.css`, written mobile-first: the base rules are the phone and min-width queries layer the rest.

| Tier | Layout |
| --- | --- |
| Phone, under 760 px | Three bands in one column. A cobalt rail band on top (brand and health pill, then the product sentence in serif; it steps aside once an answer is on the desk, and in a short landscape window). The desk in the middle (forward above answer; the authored proof sheet and a closed "what this is for" fold when empty). A cobalt composer dock along the bottom: the examples as a horizontal strip, a paper field at 16 px (a phone does not zoom on focus), a 3.4 rem send. Safe-area insets, `100dvh`, `viewport-fit=cover` and `interactive-widget=resizes-content` keep the dock above the home bar and keyboard. |
| Tablet, 760 px and up | Two panes: the rail on the left (19 to 24 rem: brand, headline, examples, composer), the desk on the right as one 42 rem column, the forward above its answer, with a corner "What this is for" link and popover. |
| Laptop, 1100 px and up | The rail widens to 27 to 35 rem and the type grows. |
| Wide, 1360 px and up | The desk becomes two columns: the forward as a serif quote beside its tall answer. |
| Short window, under 780 px tall | The rail trims its rhythm (a 5.5 rem field, a smaller headline; under 620 px no supporting line) so the composer never leaves the screen. |

Resizing a window moves between tiers live (checked below); nothing reloads and no tier is a different design. The old WhatsApp-styled column (teal header, beige ground, green bubbles) is retired.

- **The answer:** the verdict word is the headline of the proof (serif, 1.75 to 2.6 rem by width) with its icon badge, no box around it. An abstained answer has ONE dashed edge, on the answer card itself. Quotes from sources are hairline-rule quotes. Small print is at least .8 rem on a phone and .9375 rem from a tablet up.
- **Signature move, the markup:** when an answer arrives the banner settles (about 0.3 s, no bounce) and a pencil stroke is drawn under the verdict word (about 0.5 s). Abstained gets a dashed stroke that is never animated. Only under `prefers-reduced-motion: no-preference`; under reduce it is a short fade. New answers scroll into view smoothly with the forward quote and its verdict as one unit (reduced motion: instantly).
- **Colour:** one token set, defined once in the first light and first dark block (no per-width overrides), so `tests/test_ui_static.py` checks every pair in both themes at every width. The theme follows the reader's system setting; both are designed. The desk is cool newsprint in light and the near-black original in dark, with a faint static cobalt wash in its far corners (no motion: the desk is the reading surface).
- **"What this is for":** the same `scope.*` text in two placements. From a tablet up a corner link opens it as a popover over the desk (native `popover`, closes on Esc or outside click; it opens from its own top-right corner in about 160 ms with a scale from .97 and opacity, instantly under reduced motion except a short fade); the desk reserves 4.75 rem at its top so the link never sits over the first answer. On a phone it is a closed fold in the empty desk.
- **Home screen and tab:** a favicon (SVG, ICO, and a 180 px apple-touch icon; generated from `favicon.svg` by `scripts/make_icons.js`), a web manifest, and a theme colour that follows the reader's theme.
- **Unchanged rules:** an icon and a word for every verdict, abstained looks different from NEI, bands come from `/version`, no fake progress, no exclamation marks, Hindi and Punjabi strings untouched. Detector: `impeccable detect app/static` returns no findings and no advisory notes. The design record is `DESIGN.md`.

#### The living rail

The rail's background is three layers. A **CSS gradient** (cobalt, with a slow glow drifting on one transform-only layer over 48 s) always exists, and is all a phone, a reduced-motion reader, a high-contrast reader or a browser without WebGL gets. On a tablet or laptop with motion allowed, a **ShaderGradient** (the `@shadergradient/react` library) fades in over it after first paint, from a self-hosted bundle (`app/static/vendor/rail-shader.js`, 1.39 MB minified, built from `ui-src/rail-shader.jsx` by `npm run build:rail`, committed). It uses `lightType` "3d" so it never fetches the environment files the library would otherwise take from a third-party host; the library's own canvas renders at the display's refresh rate, and on a laptop the browser shares the GPU with the models the page is waiting on (measured on a real GPU, headless Chrome on the owner's RTX 4050: a fast check took 2.6 s with that canvas running against 1.1 s without a shader), so the bundle builds its own canvas with the render loop on demand, throttled to about 20 frames a second and 5 while a check is in flight, antialiasing off, pixel density 0.7 and the low-power preference; with that a fast check takes 1.25 s (the shader cost is about 0.2 s). A **legibility scrim** (the rail's deep colour at 34 to 48 percent) lies over it. `app.js` mounts it only when the window is 760 px or wider, motion is allowed, contrast is not "more", forced colours are off and WebGL exists, and unmounts it when any of those changes; a failing GPU or a missing bundle leaves the CSS gradient, silently.

Evidence (2026-10-12, headless Chrome with software GL, the page served by the real server): text on the rail was measured against the real animation at four moments, in light and dark. **Without the scrim the supporting line fell to 3.6:1 at the lightest moment (AA needs 4.5); with it the worst case is 7.1:1 on a laptop in light, 7.8:1 on a tablet, 8.7:1 in dark, and 5.9:1 on a phone's CSS gradient** (brand, headline, health pill and "Try an example" all higher). A live resize 1440 to 1000 to 700 to 390 to 1280 px, with no reload, moved between tiers and mounted and unmounted the shader as expected with no horizontal scroll; under reduced motion the shader never loaded and nothing animated; the page made 13 requests, all to its own server, with no page errors. **Not tested here:** a real GPU's frame rate and battery cost, real phones (touch, iOS Safari, the on-screen keyboard), and screen readers.

## 4. Flow and states

```
idle → typing → sending → result
                    ↘ error
```

| State | What the user sees |
| --- | --- |
| **Idle** | One line: "Paste a forwarded message. TruthLens checks it and shows you the sources." Sample chips visible |
| **Sending** | User bubble appears at once. Reply placeholder shows a spinner and "Checking…". No fake progress steps — the Phase 1 API doesn't stream, and a progress bar that isn't real is exactly the kind of dishonesty this product argues against. Streamed stage progress is P2 |
| **Result** | One verdict card per checked claim, at most 3. If `unchecked_claims` isn't empty, a footnote: "2 more claims in this message were not checked" |
| **Not a claim** | A neutral card, not a verdict card — see §5 |
| **Unsupported language** | "TruthLens works with English, Hindi and Punjabi." |
| **Error** | 422: inline under the composer ("Message is empty" / "Message is too long"). 503 or 504: a system bubble with a Retry button. The user's bubble stays |

## 5. The verdict card

### The plain card (2026-10-05): what an ordinary reader sees

TruthLens is for people who receive forwards, not for engineers. The first thing on every answer is
the **plain card**, written for a parent or grandparent, in the language of the message (see
below). It is built in the browser from fields the API already returns; nothing is
recomputed, so no number can disagree with the evaluation. In order:

1. **A plain verdict word with an icon, large:** "Probably FALSE", "Probably TRUE", "The sources
   disagree", "Not enough to decide", "Hard to say" (abstained), and for a matched published
   fact-check "Fact-checkers say: FALSE / TRUE / partly true or misleading". Never "Contradicted by
   evidence", never an absolute TRUE or FALSE for the evidence path, always "probably".
2. **One sentence of why**, e.g. "The sources I found say this is not right." (or "{publisher} has
   already checked this message."), plus, for an offline verdict only, how sure it is in words ("I am
   quite sure / fairly sure / not very sure") instead of a High or Medium band. A live verdict is
   uncalibrated and says nothing about how sure it is.
3. **What to do:** "Please don't forward it." / "Please check before you forward it."
4. **Where it comes from:** the matched fact-check ("Where this comes from"), or the closest sources
   found ("Closest sources I found": only cited passages that point the same way as the verdict, at
   most two, because offline evidence is sometimes only loosely related), or what a live look-up
   found. On an abstained offline card, no sources here.
5. **A warning when a persuasion technique is present**, in words: "This message tries to scare you,
   make you hurry."
6. **The claim that was checked**, quoted, so a long forward shows which part was judged.
7. **Two buttons:** **Listen** (the browser's own speech, in the card's language; if the device has
   no voice for it, the card says so instead of reading Hindi in an English voice) and **Copy a
   reply** (a ready message for the family group in the reader's language, with the best source link;
   nothing is sent to us).
8. **"Look this up online"** when it would help (section "Live search" below), saying exactly what it
   sends. One line: "This sends only this claim to Wikipedia and Google."
9. **"TruthLens can be wrong. Check the sources."**
10. **Details**, closed by default: the full technical card below (verdict class, confidence band,
    explanation with `[n]` citations, evidence trail, live notes, input note) and the stage trace.
    Nothing was removed; it moved.

**An offline evidence-path result is NEVER shown as a verdict (decided 2026-10-05).** When there is no
matched published fact-check and no live result, the card does not say "Probably false". If the system's lean was
"false" (it is, for almost everything, because most forwards ARE false) the card says **"Be careful with this
one": "I couldn't find a source that checks this exact claim. Most messages like this turn out to be false."**
in an amber chip; any other lean is "Hard to say". Either way it lists the closest things found ("they may not be
about this claim"), offers "Look this up online" with the reason ("To get a real answer, look it up online"), and
keeps the system's own lean only inside Details ("which is NOT reliable for free text"). Reason: on free text the evidence path mostly reflects
"forwarded claims are usually false"; in the pre-registered test it said Refuted for 122 of 125 TRUE claims and
never Supported, and it refuted "Paris is the capital of France". A verdict is shown only where one was earned:
a matched published fact-check (the fast path), or the live check that passed its pre-registered test.

**A similar fact-check (2026-10-05).** When no fact-check clears the fast-path bar but the best one scores at or
above `tau_similar` (rule and numbers: `docs/similar-factcheck-protocol.md`), a guess or abstained card says "A
similar claim was fact-checked": "{publisher} looked at something similar and rated it False. This may not be the same
message.", with the fact-check as a link, "Please read it before you forward this." and a ready reply that includes the
link. The rating is the publisher's, in words, never ours; no verdict word is used. It never replaces a live verdict.
When the fact-check's own rating cannot be mapped to True/False, it is still offered, without "rated it ...":
"{publisher} looked at something similar. This may not be the same message."

A message the claim gate does not accept gets: "I didn't find a claim to check", an example of a full sentence,
and a **"Check it anyway"** button that sends the whole text as one claim (the optional `force_claim` request
flag, off by default and never used in an evaluation). The gate refuses short fragments such as "JEE paper
leaked" (no number, name or full verb); "JEE 2025 paper leaked" is accepted.

**Which language the card speaks.** Always the language and SCRIPT of the message itself; no button
changes it, so a Punjabi forward can never come back in English because something was pressed earlier.
Hindi or Punjabi written in Devanagari or Gurmukhi is answered in
Hindi or Punjabi, but Hindi or Punjabi typed in Latin letters ("Kal se WhatsApp ke paise lagenge") is
answered in English, because the sender chose Latin letters. English is answered in English.

The page itself is for older readers: 17 px type, a column wide enough for it, buttons at least
comfortable to press, and no language buttons (the owner did not want them: the page follows the
browser's language, or `?lang=hi|pa` for a demo, and each answer follows its message's own script), and the demo examples folded under "Try an
example" so the first screen is a paste box and a short instruction. The test for whether it works
is `docs/usability-test.md` (relatives, with pass bars fixed before testing).

### The technical card (inside Details)


```
┌──────────────────────────────────────┐
│ ✕  REFUTED                     High  │  verdict chip · confidence band
│ Claim: "Drinking hot water kills…"   │  the checked claim, normalized
│──────────────────────────────────────│
│ 🔎 Checked against evidence          │  path badge
│ The WHO states … [1] … contradicts   │  explanation with citation markers
│ the claim that … [3]                 │
│──────────────────────────────────────│
│ ▸ See evidence (3)                   │  evidence trail, collapsed
│ ⚠ Fear appeal · False urgency        │  manipulation flags (P2)
│──────────────────────────────────────│
│ Hindi, typed in Roman script →       │  what the system did to the input
│ converted to Devanagari              │
│ TruthLens can be wrong. Check the    │
│ sources.                             │
└──────────────────────────────────────┘
```

### Field mapping

| Element | Response field |
| --- | --- |
| Verdict chip | `results[i].verdict`, `abstained` |
| Confidence band | `results[i].confidence` |
| Claim line | `results[i].claim.text` |
| Path badge | `results[i].path`, `match` |
| Explanation | `explanation`, markers from `cited` |
| "Couldn't generate an explanation" note | `explanation_source == "template"` — shown small and neutral, not as an error |
| Evidence trail | `passages[]`: `title`, `url`, `stance`, `text`, `highlight` |
| Fast-path source | `match.publisher`, `match.title`, `match.url` |
| Input note | `input.lang`, `input.script`, `input.transliterated` |
| Manipulation row | `manipulation_flags` — hidden when empty |

### Evidence trail, expanded

Each passage is a row: stance tag (Supports / Refutes / Neutral), source title and domain, and the passage text with the `highlight` span marked. The citation number matches the explanation's `[n]` marker, and tapping a marker scrolls to its row. The trail is rendered from the response, never recomputed in the browser.

On the fast path, the trail shows the matched fact-check instead: publisher, headline, link, and the words "Already checked by [publisher]".

### Live search (post-test)

Cards below the High band that did not come from a published fact-check show a
button, "Search Wikipedia & fact-checkers", with its privacy note beside it ("This
sends the claim to Wikipedia and Google Fact Check"). One click sends only that
claim. The card is then replaced by a live card:
- a 🌐 line naming the sources queried, and Wikipedia's CC BY-SA attribution;
- **a verdict, but no confidence band**, only when the two models agree (the chip shows the
  verdict word and icon as usual). The notes under it say: "This verdict comes from Wikipedia
  text, read by two models that had to agree", the pre-registered test result in plain words
  ("In a test on 350 claims it was right 94% of the time when it gave a verdict, and it gave one
  for only about 3 claims in 10"), and "Confidence for online results has not been calibrated";
- when the models do not agree, or are not sure enough, the card is **abstained** ("Not confident
  enough to judge") with the note "The two models did not agree, or were not sure enough, so
  there is no verdict. Read the sources.";
- the sources, open by default, relevance-ordered, each tagged Wikipedia or Fact-check; a
  fact-check shows its publisher's own rating.
If a source is down the earlier answer stays and the note under the button says so.

### Word view and greeting (2026-10-05)

- **"Which words mattered?"** appears on a live Supported/Refuted verdict card only (`/version` `config.word_view`), never on a fast-path,
  careful, similar or hard-to-say card. One tap shows the claim with up to three words marked with a **mark and a ▲ glyph (never colour
  alone)**, a one-line hint, a note when the words are those of the English version of a Hindi/Punjabi message, and the one source
  sentence that mattered most; a second tap folds it away. If the server cannot compute it, it says so and the card is unchanged.
- **"Why: this is what the source says"** appears on a live Supported/Refuted card only: the one sentence of the best-agreeing Wikipedia
  passage that shares the most words with the claim, quoted as written (extractive, so nothing is generated), with its source link; a
  Hindi or Punjabi card says the source is in English. A fast-path answer has no such text on file (only the fact-check's headline, already
  shown), so it shows none. Frontend only (`sourceQuote` in `app.js`).
- A message that is only a greeting or blessing shows "Just a greeting: nothing here to check" with no "Check it anyway" button
  (`gate_reason: "greeting"`); a short fragment keeps the button.

## 6. Visual language for verdicts

**Colour is never the only signal.** Every verdict has an icon *and* a word.

| Verdict | Icon | Colour role | Label (EN) | Label (HI) |
| --- | --- | --- | --- | --- |
| Supported | ✓ | green | Supported by evidence | सबूतों से पुष्ट |
| Refuted | ✕ | red | Contradicted by evidence | सबूतों से खंडित |
| Conflicting | ⇄ | amber | Evidence disagrees | सबूत आपस में टकराते हैं |
| NEI | ? | grey | Not enough evidence | पर्याप्त सबूत नहीं |
| NotAClaim | 💬 | neutral, no chip | Nothing here to fact-check | इसमें जाँचने लायक कोई दावा नहीं है |
| **Abstained** (any verdict) | ◌ | grey, **dashed border** | Not confident enough to judge | भरोसे से फ़ैसला नहीं कर सकते |

Punjabi strings go in `pa.json` and Hindi in `hi.json`; both were reviewed by a native speaker before the demo (`docs/i18n-review.md`). Wrong Punjabi in a Punjabi demo is worse than English, so any new string needs the same review.

**Abstained is visibly different from NEI.** NEI says the evidence is missing. Abstained says the system doesn't trust its own answer. When abstained, the card shows the would-be verdict small and greyed — "Leaning: Refuted" — so the evaluator can see the system has an opinion and chose not to commit to it. That single detail makes the abstention story concrete in the demo.

## 7. Confidence display

Show a **band**, not a percentage. "73%" invites false precision and reads as a probability the user should trust.

| Band | Rule |
| --- | --- |
| High | confidence ≥ upper cut |
| Medium | between the cuts |
| Low | below the lower cut but ≥ τ_abstain |
| — | below τ_abstain: the card is in the abstained state instead |

The cut points come from the calibration curve on dev, served in `/version` alongside τ_abstain, and are never hard-coded in JavaScript. Hovering the band shows the exact value with "calibrated on the development set" — the detail is there for the evaluator who asks, without leading with it.

## 8. Copy principles

- Plain words. "Contradicted by evidence", not "Refuted".
- Never "true" or "false". The system judges evidence, not truth.
- No exclamation marks, no alarm language, even for Refuted.
- The explanation is in the input's language. When Punjabi falls back (cut item 3), the card says so: "Explanation in Hindi — Punjabi explanations aren't available yet."

## 9. Accessibility

| Requirement | How |
| --- | --- |
| WCAG AA contrast | All text and chips, in both light and dark mode |
| Keyboard | Enter sends, Shift+Enter new line, Tab reaches every control, the evidence expander is a real `<button>` |
| Screen readers | Result container is `aria-live="polite"`; the verdict chip has a full-text `aria-label` |
| Motion | Respects `prefers-reduced-motion` — no spinner animation, text "Checking…" only |
| Language | Each card sets `lang="hi"` or `lang="pa"` on its explanation so screen readers use the right voice |
| Theme | Follows `prefers-color-scheme`; colours defined as CSS custom properties |

## 10. Out of scope for this release

User accounts, history, sharing a result, uploading images or screenshots, browser extensions, real messaging integration.

## 11. Demo script

Six canned forwards, one per path, wired to the sample chips (`app/static/samples.json`, our own wording — never dataset text). Run `python scripts/demo_check.py` before every demo: it sends all six (and the regression forwards) through the served pipeline and exits 1 if a chip no longer shows its path. If one breaks, swap the chip, don't improvise.

| # | Chip | Input | Shows |
| --- | --- | --- | --- |
| 1 | EN, fact-checked | "Pineapple juice is 500 times more effective at stopping a cough than cough syrup" | Fast path, "Already checked by …" (cosine 0.92 ≥ τ_match 0.90) |
| 2 | Roman Hindi | "Kal se WhatsApp ke paise lagenge" | Transliteration note + evidence path (chosen by the rule in `scripts/pick_romanized_chip.py`; the earlier "6000 rupaye" chip was refuted from a fact-check about a US stimulus cheque, so it stays in `regression` as a known weak case) |
| 3 | ਪੰਜਾਬੀ | "ਸਰਕਾਰ ਹਰ ਕਿਸਾਨ ਨੂੰ ਮੁਫ਼ਤ ਟਰੈਕਟਰ ਦੇ ਰਹੀ ਹੈ" | Gurmukhi input, explanation-language fallback note |
| 4 | Long forward | A Roman-Hindi rant with one claim (lemon water cures cancer) among filler | Claim extraction: only the claim is checked; manipulation flags |
| 5 | Greeting | "Good morning, stay blessed 🙏" | NotAClaim card |
| 6 | Thin evidence | "ਲਾਹੌਰ ਪਾਕਿਸਤਾਨ ਦੇ ਪੰਜਾਬ ਸੂਬੇ ਦੀ ਰਾਜਧਾਨੀ ਹੈ" | Abstained card with "Leaning: …" |

**Live verdict (optional, needs the network and the key in `.env`).** After step 6, press "Search Wikipedia & fact-checkers" on a free-text claim such as "Hyderabad is the capital of Telangana": the card gets a verdict when two models agree, with the notes under it that say what that means and how it was tested (94% of its answers right in the test, an answer for only about 3 claims in 10). On a claim the models cannot settle it says there is no verdict and lists the sources. Click the claim once beforehand so the responses are cached; do not click on many claims in quick succession (Wikipedia rate-limits at about 50 requests a minute).

Order for a live demo: 5, 1, 2, 6. Showing "nothing to check" first proves the system doesn't label everything, and ending on an abstention lands the project's central argument.

**Chip 1 and τ_match.** At the served τ_match 0.90 (chosen on dev) the fast path fires only on near-verbatim restatements of an indexed claim: correct matches for paraphrases of well-known hoaxes scored 0.75–0.86 (Phase 7 log). τ was not lowered for the demo; the chip is a phrasing that clears it.

`?lang=hi` or `?lang=pa` on the URL switches the interface language for a demo; otherwise the browser's language is used. The Hindi and Punjabi strings were reviewed by a native speaker on 2026-10-02 (`docs/i18n-review.md`).
