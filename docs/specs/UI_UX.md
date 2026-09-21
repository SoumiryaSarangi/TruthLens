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

Punjabi strings go in `pa.json` and **need a native speaker's review** before the demo. Hindi strings should get the same check. Wrong Punjabi in a Punjabi demo is worse than English.

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

Six canned forwards, one per path, wired to the sample chips. Run through all six before every demo; if one breaks, swap the chip, don't improvise.

| # | Input | Shows |
| --- | --- | --- |
| 1 | English claim with a published fact-check | Fast path, "Already checked by …" |
| 2 | Romanized Hindi claim | Transliteration note + evidence path |
| 3 | Gurmukhi Punjabi claim | Punjabi input, language fallback note if applicable |
| 4 | Long emotional rant, one claim inside | Claim extraction |
| 5 | "Good morning, stay blessed 🙏" | NotAClaim card |
| 6 | Claim with thin evidence | Abstained card with "Leaning: …" |

Order for a live demo: 5, 1, 2, 6. Showing "nothing to check" first proves the system doesn't label everything, and ending on an abstention lands the project's central argument.
