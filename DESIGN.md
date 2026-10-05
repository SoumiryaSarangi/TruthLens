---
name: TruthLens
description: A proof desk for forwarded messages. A cobalt rail to paste into, a newsprint desk where each verdict is marked with one word and one pencil stroke.
colors:
  cobalt-rail: "#1636a8"
  cobalt-rail-dark: "#0f1f66"
  rail-ink: "#ffffff"
  rail-ink-dark: "#f3f6fc"
  desk-newsprint: "#e7eaee"
  desk-newsprint-dark: "#0a0e15"
  sheet: "#ffffff"
  sheet-dark: "#151b26"
  forward-tint: "#dde5fb"
  forward-tint-dark: "#1b2748"
  ink: "#0e1520"
  ink-dark: "#e8edf4"
  ink-muted: "#46525e"
  ink-muted-dark: "#a3afbd"
  rule: "#b4bcc7"
  rule-soft: "#d3d9e0"
  link-cobalt: "#1636a8"
  link-cobalt-dark: "#93b3ff"
  supported-fg: "#0b6b2f"
  supported-bg: "#e3f5e8"
  refuted-fg: "#a11a1a"
  refuted-bg: "#fde8e8"
  conflicting-fg: "#7a4500"
  conflicting-bg: "#fff1d6"
  nei-fg: "#3f4a54"
  nei-bg: "#eceff1"
  abstained-fg: "#3f4a54"
  abstained-bg: "#f4f5f6"
  error-fg: "#a1190f"
  error-bg: "#fdeceb"
  phone-teal: "#075e54"
  phone-ground: "#efeae2"
  phone-out-bubble: "#d9fdd3"
typography:
  display:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, Nirmala UI, serif"
    fontSize: "clamp(2.1rem, 3.1vw, 3.1rem)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  verdict:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, Nirmala UI, serif"
    fontSize: "clamp(2rem, 2.5vw, 2.6rem)"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.01em"
  quote:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, Nirmala UI, serif"
    fontSize: "1.2rem"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "system-ui, Segoe UI, Nirmala UI, Noto Sans Devanagari, Noto Sans Gurmukhi, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  reason:
    fontFamily: "system-ui, Segoe UI, Nirmala UI, Noto Sans Devanagari, Noto Sans Gurmukhi, sans-serif"
    fontSize: "1.08rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, Segoe UI, Nirmala UI, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.5
  indic:
    fontFamily: "system-ui, Segoe UI, Nirmala UI, Noto Sans Devanagari, Noto Sans Gurmukhi, sans-serif"
    fontSize: "inherit"
    lineHeight: 1.7
    letterSpacing: "0"
rounded:
  hairline: "0.25rem"
  sm: "0.5rem"
  md: "0.8rem"
  lg: "1.1rem"
  pill: "1.4rem"
  round: "50%"
spacing:
  xs: "0.4rem"
  sm: "0.75rem"
  md: "1.1rem"
  lg: "2.25rem"
  rail-pad: "2.5rem"
  desk-gap: "3rem"
components:
  rail:
    backgroundColor: "{colors.cobalt-rail}"
    textColor: "{colors.rail-ink}"
    padding: "1rem 2.5rem"
  desk:
    backgroundColor: "{colors.desk-newsprint}"
    textColor: "{colors.ink}"
    padding: "2.5rem 3rem 3rem"
  answer-card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "1.5rem 1.75rem 1.25rem"
  forward-quote:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.quote}"
    padding: "1rem 0 0"
  verdict-supported:
    textColor: "{colors.supported-fg}"
    typography: "{typography.verdict}"
  verdict-refuted:
    textColor: "{colors.refuted-fg}"
    typography: "{typography.verdict}"
  verdict-conflicting:
    textColor: "{colors.conflicting-fg}"
    typography: "{typography.verdict}"
  verdict-nei:
    textColor: "{colors.nei-fg}"
    typography: "{typography.verdict}"
  verdict-abstained:
    backgroundColor: "{colors.abstained-bg}"
    textColor: "{colors.abstained-fg}"
    typography: "{typography.verdict}"
  button-pill:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.link-cobalt}"
    rounded: "{rounded.pill}"
    padding: "0.3rem 1rem"
    height: "2.75rem"
  button-pill-hover:
    backgroundColor: "#e3e9fb"
  button-send:
    backgroundColor: "{colors.rail-ink}"
    textColor: "{colors.cobalt-rail}"
    rounded: "{rounded.round}"
    size: "3.4rem"
  composer-field:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "1rem 1.2rem"
    height: "8.5rem"
  error-bubble:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error-fg}"
    rounded: "{rounded.lg}"
    padding: "0.55rem 0.75rem"
---

# Design System: TruthLens

## Overview

**Creative North Star: "The Proof Desk"**

A check is a proof being marked, not a chat. On a laptop (1100 px and up) the page is two panes: a saturated cobalt rail on the left where you paste and try an example, and a cool newsprint desk on the right where every answer sits beside the forward it answers. The world is a newspaper proof sheet read by an editor. It lends type (a system serif for display and quoted text), palette, density and one signature move. It never supplies the navigation or controls, which stay standard: a textarea, pill buttons, details folds.

The reader is often a parent or grandparent, so the system is calm and plain. One word, one pencil stroke under it, one sentence of why, the source quoted, what to do. When the system cannot decide, the card looks different (grey, dashed) so unsureness is visible without reading.

Below 1100 px the earlier single-column chat (WhatsApp-style: teal header, beige ground, 440 px column, white and pale-green bubbles) is deliberately unchanged because the owner pinned it. It is a separate, frozen world; do not mix its tokens into the desk.

**Key Characteristics:**
- Cobalt rail, grey desk, near-black ink; verdict colours are state roles only, never decoration.
- System serif for the rail headline, the forwarded quote and the verdict word; system sans for everything operable.
- One signature: the markup, a hand-drawn stroke under the verdict word.
- Flat tonal surfaces; one soft shadow for the answer card.
- Offline, system fonts only, no web fonts, no images.

## Colors

A restrained palette: one cobalt, cool neutrals, and five verdict colour pairs that only ever signal state. Every text-on-background pair is a token; the light and dark pairs are defined in styles.css (a first light block, a first dark block, then a desktop override pair that comes after on purpose, because tests/test_ui_static.py reads only the first light and first dark block). Desktop values are therefore AA-checked by script, not by that test.

### Primary
- **Proofreader's Cobalt** (`cobalt-rail`): the rail background, links, focus ring, button text, the send arrow. Dark mode deepens the rail to `cobalt-rail-dark` and lightens links and focus to `link-cobalt-dark`.

### Neutral
- **Cool Newsprint** (`desk-newsprint`): the desk ground. Dark: `desk-newsprint-dark`.
- **Clean Sheet** (`sheet`): answer cards, composer field, pill buttons. Dark: `sheet-dark`.
- **Forward Tint** (`forward-tint`): the --bubble-out token; on the desk the forward is transparent, so it paints nothing at 1100 px and up. Do not use it for new desk surfaces.
- **Ink** (`ink`) and **Quiet Ink** (`ink-muted`): text and secondary text. Dark variants carry the same roles.
- **Rule** and **Soft Rule** (`rule`, `rule-soft`): hairlines, borders, trail-item outlines.

### Verdict roles (state only)
- **Supported green**, **Refuted red**, **Conflicting amber**, **Not-enough-evidence grey** (`nei-*`), **Abstained grey** (`abstained-*`): each a foreground and a tinted background. Each also has a dark-mode pair. They colour the verdict word, its icon badge, stance tags and the proof-sheet marks. Colour is never the only signal.
- **Error** (`error-fg`, `error-bg`): error bubble and composer error only.

### Phone world (frozen, below 1100 px)
- `phone-teal`, `phone-ground`, `phone-out-bubble`: the WhatsApp-style chat. Not for desk surfaces.

### Named Rules
**The Colour-Is-State Rule.** Green, red, amber and grey mean a verdict and nothing else. Cobalt is the only brand colour; it never stands for a verdict.

**The Two-Pair Rule.** A new text and background pair is added as a token in light and dark and checked for 4.5:1 in both, desktop included.

## Typography

**Display Font:** system serif stack (Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, Nirmala UI), token `--serif`.
**Body Font:** system-ui, Segoe UI, Nirmala UI, Noto Sans Devanagari, Noto Sans Gurmukhi, sans-serif.

**Character:** an editor's serif for what is quoted and decided, a plain system sans for what is read and pressed. Nothing is downloaded; the demo works offline.

### Hierarchy
- **Display** (700, clamp(2.1rem, 3.1vw, 3.1rem), 1.1): the rail's first sentence.
- **Verdict** (700, clamp(2rem, 2.5vw, 2.6rem), 1.12; Hindi and Punjabi clamp(1.7rem, 2.1vw, 2.2rem) at 1.5, in the sans): the verdict word with its stroke.
- **Quote** (400, 1.2rem, 1.5, max 34ch): the forwarded message in the narrow column. The quote caption ("Forwarded") is sans, 600, .82rem.
- **Reason** (400, 1.08rem, 1.5): the one sentence of why. Source quotes use the serif at 1.05rem.
- **Body** (400, 0.9375rem = 15px, 1.5): base size, follows the reader's text-size setting (rem, not px).
- **Label** (.88rem to .95rem): buttons, folds, sources. Small print (disclaimer, trace, domain, notes) is .9rem on desktop and never smaller than .78rem on the phone column.

### Named Rules
**The Indic Room Rule.** Hindi and Punjabi text gets letter-spacing 0 and line-height 1.7 (1.4 to 1.5 in display sizes). Forwarded text carries no lang attribute, so its body is always 1.65. Never track or clip matras and conjuncts.

**The Serif-For-Quotes Rule.** The serif is for the rail headline, the forwarded quote, source quotes and the verdict word. Controls, labels and sources are sans.

## Layout

Two modes, split at 1100 px. At 1100 px and up, `.phone` becomes a grid: a rail column of clamp(27rem, 34vw, 35rem) and a desk filling the rest. The rail stacks topbar, hero (headline plus one short line), then the bottombar (composer, examples open as a wrapped chip grid), with 2.5rem side padding. The desk (padding 2.5rem 3rem 3rem) is a two-column grid, 20rem forward beside 42rem answer, 3rem column gap and 2.25rem row gap, centred.

Between 1100 and 1359 px the desk is one column of 42rem: the forward sits above its answer (row gap 1rem). From 1360 px the forward is sticky (top 1.5rem) beside a tall answer. Layout breakpoints are 1100 and 1360, and nothing else.

Below 1100 px: one 440 px column, full width on phones, header, scrolling chat, bottom composer. Rhythm in both is rem-based, steps of about .25 to .5rem inside components and .75 to 2.25rem between them. Tap targets are at least 2.5rem, buttons 2.75rem.

## Elevation & Depth

Mostly flat, tonal layering: rail, desk and sheet are three flat tints. The only lift is the answer card (`0 1px 2px rgba(14,21,32,.08), 0 12px 24px -10px rgba(14,21,32,.24)`, dark variant darker) and, on the empty desk, a soft drop shadow under the proof sheet. The composer has a small soft shadow on the rail so it reads as paper. Shadows are soft and ambient, never offset or hard. An abstained answer drops its shadow and takes a 2px dashed edge instead.

### Named Rules
**The Flat-Rail Rule.** The rail has no shadow and no border; depth is the contrast of cobalt against newsprint.

## Shapes

Soft but not bubbly. Answer card and composer 1.1rem radius, verdict icon badge a circle, buttons and example chips full pills (1.25 to 1.4rem), evidence rows and stance tags small (.5rem and .25rem). On the desk the forward quote has no box at all: a 2px ink rule above it, like a proof column. Quotes from sources are a 1px left hairline, not a grey box. The first-level silhouette to remember is the circular icon badge beside a large serif word.

## Components

### Rail (topbar, hero, bottombar)
Cobalt field, white ink. Topbar: a drawn search-and-check icon, brand in serif 1.35rem 700, and a health pill (translucent white; a dot beside its text; becomes solid with a border under reduced transparency and more contrast). Hero: serif headline and a 1.05rem supporting line at 88 percent ink. Bottombar: the examples fold, then the composer.

### Composer and send
A paper textarea, 8.5rem minimum, 1.08rem text, 1.1rem radius, no border on the rail, 3px white focus ring. Send is a 3.4rem white circle with a cobalt drawn arrow, bottom right. In dark mode the field turns pale (#eef2ff) so it still reads as paper on the deep rail. The composer error is white 600 text under the field with its own role="alert".

### Desk feed pair
Each check is a row. The forward (`.bubble.out`) is a transparent serif quote under a 2px ink rule with a bold sans caption. The answer (`.bubble.in` with `.card.plain`) is a white sheet with the desk shadow. Inside: verdict banner, one reason sentence, an action line (650 weight), the quoted source, a claim line, actions, and folds.

### Verdict banner (the signature)
The verdict word is set at display scale in the serif with a round icon badge (3.2rem, tinted 16 percent of the verdict colour) to its left, no box. Under the word, a pencil stroke (SVG path, 4px, round caps, 80 percent opacity) in the verdict colour. When a check returns the banner is stamped (opacity and a 1.04 to 1 settle with a 3px blur, .3s) and the stroke is drawn once (stroke-dashoffset, .5s, after .22s). Abstained: the stroke is dashed and never animated, the card has a 2px dashed grey edge on grey, and the word is still shown with its icon. Hindi and Punjabi verdicts switch to the sans.

### Buttons
Pills with a 1px rule border, white fill, cobalt text, 2.75rem tall: `.act` (listen, copy, force-check, word view), `.live-btn` (search online), `.retry`, and example chips `.sample` (2.5rem). Hover (pointer devices only) tints to `#e3e9fb` and underlines folds; press scales .97 under no-preference motion. Focus is a 2px outline offset 2px in cobalt (light-blue in dark).

### Folds
`details.more` (Details, with a hairline top rule and cobalt summary), `details.examples` (white summary on the rail), `details.trace` (muted small summary). The chevron is drawn with borders and rotates from -45 to 45 degrees; the body animates height and opacity where `interpolate-size` is supported. Never a typed glyph.

### Evidence trail
A toggle button with a drawn chevron opens a list of bordered rows (1px soft rule, .5rem radius): a stance tag (Supports green, Refutes red, Neutral grey, uppercase .8rem), the source link and domain, and the passage with `mark` highlighting. A cited row flashes a 2px cobalt outline. Sources on the card are a plain bulleted list of links.

### Band meter
A pill with a 1px rule, three small bars that fill by High, Medium or Low, and the word. The word carries the meaning; the bars only echo it. The band comes from the `/version` response and is shown only when present.

### Error states
Error bubble: tinted red surface, inset 1px red edge, a drawn icon, a message and a Retry pill, laid in the answer column. Composer error: icon and text under the field. Both state what happened in plain words.

### Proof-sheet empty state
Before any check the desk shows one large authored SVG (aria-hidden, no copy): a back sheet rotated slightly, a paper sheet with a dashed margin, crop marks, ruled lines, six editor's marks in the six verdict colours (tick, cross, double arrow, query, dashed ring, wavy) each with a pencil underline. The marks draw in sequence on load under no-preference motion. The phone column keeps its icon and one sentence instead.

### Motion
One easing token, `--ease-out: cubic-bezier(.23, 1, .32, 1)`, critically damped, no overshoot. Motion only under `prefers-reduced-motion: no-preference`: reply arrival (.22s to .28s), stamp, stroke draw, fold open, press scale, and on desktop a rise-in of rail parts and proof-sheet rows. Under `reduce`: the spinner is hidden ("Checking…" text only) and every entrance becomes a .15s opacity fade; nothing moves.

## Do's and Don'ts

### Do:
- **Do** give every verdict a drawn icon and its word; colour only reinforces.
- **Do** keep abstained distinct: grey, dashed edge, dashed unanimated stroke, "Leaning" only inside Details.
- **Do** read confidence bands from `/version`; with no bands show none.
- **Do** show "Checking…" and nothing else while waiting.
- **Do** set Hindi and Punjabi at letter-spacing 0 and tall leading (1.7; 1.4 to 1.5 in display sizes).
- **Do** use `--ease-out` for every entrance and gate motion on `prefers-reduced-motion: no-preference`.
- **Do** draw chevrons and icons as CSS or inline SVG; keep controls at 2.5rem tall or more.
- **Do** keep verdict colours as state roles and add new colour pairs as tokens checked at 4.5:1 in light and dark.

### Don't:
- **Don't** float the phone column in a desktop browser, or turn the desk into a dashboard of tiles.
- **Don't** use exclamation marks in any string.
- **Don't** add fake progress (bars, percentages, rotating messages).
- **Don't** invent a verdict colour or use cobalt for a verdict.
- **Don't** use web fonts, images or network assets; the demo must run offline.
- **Don't** put desk tokens into the phone world below 1100 px, or edit the phone column's look; the owner pinned it.
- **Don't** put desktop tokens inside the first light or first dark block; the desktop overrides stay after them.
- **Don't** add hard offset shadows or typed glyph icons or chevrons.
