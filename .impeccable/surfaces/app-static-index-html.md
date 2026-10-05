---
version: 1
slug: "app-static-index-html"
primary_target: "app/static/index.html"
related_targets: []
---

# TruthLens desktop workspace

**Scope and mode:** Operate. The whole `app/static` surface at laptop and desktop widths (1100 px and up); phone widths keep the single chat column built earlier. Visitor: a reader checking a forwarded message, often a parent or grandparent, plus an evaluator with five minutes.

**Audience, job, proof, constraints:** paste a forward, understand the answer in five seconds, see where it comes from, know when the system cannot decide. Every verdict keeps an icon and a word; abstained is grey, dashed, with a "Leaning" line in Details; confidence is a band from `/version`; no fake progress ("Checking…" only); no exclamation marks. System fonts only, vanilla JS, offline, strings only from `app/static/i18n/*.json` (hi and pa were reviewed and are frozen). The layout was pinned by the owner on 2026-10-05: a full desktop workspace (not a phone frame), confident and editorial, replace in place on branch `ui-restyle`. The owner's pinned direction beats the concept roll (seed key c4ac5c88, assigned index 3 was not used).

**Chosen direction and memorable moment:** the proof desk. World: a newspaper proof sheet, marked by an editor. It lends type (a system serif for display and quoted forwards, system sans for controls), palette, density and ONE signature move; it never supplies the navigation or the controls, which stay standard (a textarea, buttons, details folds).
Signature move: the **markup**. When a check returns, the verdict banner is stamped onto the sheet (a quick settle, no bounce) and an editor's pencil stroke is drawn under the verdict word (stroke-dashoffset, about 600 ms). The same stroke is the mark over the words that mattered in the word view. Abstained gets a dashed stroke that is not animated.

**Unresolved decisions:** none blocking. A fast-path word view and a per-fact-check "why" were measured and are off; the desktop layout does not depend on them.

## Direction contract

THESIS: a check is a proof being marked, not a chat. Two panes on a laptop: the rail to paste and to try an example, the proof desk to read the answers, each answer laid beside the forward it answers. It refuses the phone column floated in a desktop browser, and the dashboard of tiles.

OWN-WORLD: a saturated cobalt "proofreader's pencil" field owns the left rail (30 to 40 percent of the screen); the desk is cool newsprint grey, ink near-black; verdict colours (green, red, amber, grey) are state roles only. Display type is a system serif at large size, UI and body are the system sans; Devanagari and Gurmukhi use the same stacks with zero tracking and tall leading. Recognisable with content removed: a blue rail, a grey desk, a hand-drawn pencil stroke under one word, quote and answer side by side.

STORY: the reader pastes, sees "Checking…", then watches the answer settle on the sheet: one word, one stroke, one sentence of why, the source quoted, what to do. They believe it because the source sits beside it, and they can tell when the system is unsure because that card looks different.

FIRST VIEWPORT: at 1440 x 900, a cobalt rail 480 px wide holds the brand and health pill at the top, then the product sentence from `intro` set large in the serif (first sentence as the headline, the rest as a short line), then a paper composer (large textarea, round send button, 48 px) with the examples open as a chip grid below. The desk fills the rest: before any check it shows one large authored proof sheet (aria-hidden SVG: ruled lines, six editor's marks in the six verdict colours, no copy); after a check each answer is a row with the forward as a serif quote in the narrow column and the plain card in the wide column. The primary action (send) sits in the rail under the composer.

FORM: Operate shell with a signature move; position 3 of the grounded list was set aside because the owner pinned the direction; seed key c4ac5c88.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
