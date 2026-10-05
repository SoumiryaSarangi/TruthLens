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

Desktop: a centred phone-width column, max 440 px, so it reads as a phone in a projector demo. Mobile: full width.

**Sample chips** fill the composer with a canned forward, one per path in §11. They exist so a live demo never depends on typing Hindi on a projector keyboard.

### Desktop workspace (2026-10-05, owner's request; supersedes "a centred phone-width column" at 1100 px and up)

On a laptop or desktop (1100 px and wider) the page is a two-pane **proof desk**, not a phone floated in a browser. Below 1100 px nothing changes: the
single 440 px chat column above is the page, and it stays WhatsApp-styled on purpose (the owner pinned it). Layout, tokens and rules, all in `styles.css`
(the desktop block and its overrides at the end of the file):

- **Rail (left, 27 to 35 rem, cobalt):** brand and health pill, the product sentence set large in the serif (the first sentence of `intro` is the
  headline, the rest a short line; set by `app.js` from the existing string, no new copy), the composer (large textarea, round send button) and the
  examples, open by default on a laptop.
- **Desk (right, cool newsprint):** each check is a row. At 1360 px and up the forward is a serif quote in a narrow column (sticky beside a tall answer)
  and the plain card is in the wide column; from 1100 to 1359 px the quote sits above the card, one column. Before the first check the desk shows an
  authored proof sheet (decorative SVG, no copy): six editor's marks in the six verdict colours against ruled columns.
- **The answer at desk scale:** the verdict word is the headline of the proof (serif, about 2.5 rem) with its icon badge, no box around it. An abstained
  answer has ONE dashed edge, on the answer card itself. Quotes from sources are hairline-rule quotes. Small print is at least .9 rem.
- **Signature move, the markup:** when an answer arrives the banner settles (about 0.3 s, no bounce) and a pencil stroke is drawn under the verdict word
  (about 0.5 s). Abstained gets a dashed stroke that is never animated. Only under `prefers-reduced-motion: no-preference`; under reduce it is a short fade.
- **Colour:** the desktop token pair (`--bar-bg` cobalt, `--app-bg` newsprint, `--serif`) comes after the first light and dark blocks because
  `tests/test_ui_static.py` reads those only. The desktop values were checked for WCAG AA by script on 2026-10-05: every test pair plus the new
  pairs (verdict colours on the card and on the abstained ground, links and muted text on the quote ground, the 88% white rail text on cobalt at 8.07:1 light
  and 11.62:1 dark) pass in light and dark. A change to a desktop token must repeat that check.
- **"What this is for":** the same `scope.*` text in two placements. On a laptop it is open under the proof sheet on the empty desk (two columns, "Built for" and "Not built for"), and a "What this is for" link in the top-right corner opens it again as a popover at any time (native `popover`, closes on Esc or outside click); both go away with the empty state or the popover. On a phone it is a closed fold in the empty chat. Contents: built for short forwarded claims in en, hi, pa including Roman script, best when a fact-checker has seen the claim or Wikipedia can settle it; not built for recent events, private or local events, opinions and predictions, very short fragments, or anything with no source (it says "Hard to say" and does not guess). Questions are NOT excluded: they are checked like claims. hi/pa are machine-drafted (`docs/i18n-review.md`).
- **Unchanged rules:** an icon and a word for every verdict, abstained looks different from NEI, bands come from `/version`, no fake progress, no
  exclamation marks, Hindi and Punjabi strings untouched. Detector: `impeccable detect app/static` returns no findings. The design record is `DESIGN.md`.

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
