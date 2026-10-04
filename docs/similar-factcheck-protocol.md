# The "similar fact-check" card: how its threshold is chosen (rule fixed before the dev numbers are read)

Written and committed 2026-10-05 BEFORE the development-split curve is read for this purpose. Approved by
the project owner the same day.

## Why

On 30 typical WhatsApp hoaxes only 1 reached the fast path (cosine >= tau_match 0.90), yet the matching stage
had found a relevant published fact-check for most of the rest at scores between about 0.55 and 0.77 (for
example "WhatsApp will start charging users" -> BOOM's "Viral Messages Claiming WhatsApp Will Become Chargeable
Are ..."). The strict threshold exists because a verdict taken from a wrong match is harmful. A SUGGESTION is
different: "a fact-checker looked at something similar; this may not be the same message; please read it" makes
no claim about the reader's message, shows the publisher's own rating as the publisher's, and sends the reader
to a source. It can therefore sit at a lower threshold than a verdict.

## What it is

An additive field on a claim's result: `similar_match`, set when the best fact-check scores at or above
`tau_similar` and below `tau_match`. It changes no decision: the path, the verdict, the confidence, the
abstention and every reported number are exactly what they were. It is off unless `tau_similar` is set.

## The rule for tau_similar (fixed now)

On the MultiClaim DEV posts, with BGE-M3 and no reranker (run `da5132cee8a0`, the stored coverage curve),
**tau_similar is the lowest stored curve threshold at which the precision of the posts scoring at or above it
is still at least 0.70**, rounded UP to two decimals. Precision here is the fast path's own definition: the
share of those posts whose top-1 fact-check is one of the post's gold fact-checks. It is a LOWER bound on
real precision (MultiClaim's annotation is incomplete: a fact-check outside the gold set can still be right).

The test split is used once, as a check and not a choice: the stored test predictions (run `891eecc6a90e`)
are read at the chosen threshold and the row is reported next to the dev row. If the test precision at that
threshold is below 0.60, the card is NOT shipped (the dev choice did not hold out of sample).

## What is reported

The dev and test rows (threshold, coverage, precision); the 30 hoaxes of the probe answered with the card; the
wording of the card; and the limit that precision here is measured on real MultiClaim posts, not on short clean
statements, and that "similar" is not "the same".

## Result of applying the rule (2026-10-05)

Dev curve, run `da5132cee8a0` (3,153 posts): precision 0.742 at threshold 0.8517 (coverage 4.8%, 151 posts),
0.688 at 0.8169 (9.5%), 0.661 at 0.7909, 0.651 at 0.7705 and at 0.7514 (23.8%), 0.636 at 0.7064 (38.1%), 0.599
at 0.6678 (52.4%). **The rule picks 0.8517, rounded up to `tau_similar` = 0.86.**

Test check (stored predictions, run `891eecc6a90e`, read once at the chosen threshold, not used to choose it):
at 0.8545 coverage 4.8%, precision 0.768 (>= the 0.60 floor, so the card ships).

**What this means, said plainly.** The promise made when this was proposed ("70-72% right at scores 0.75 to
0.81, answering 10 to 24% of posts") was read from the TEST curve; the DEV curve, which governs, is lower: 65 to
69% in that range. Under the rule as fixed, the card appears for about 4.8% of real posts (against 1.7% for the
verdict path), and for NONE of the 30 typical hoaxes probed (their best matches score 0.55 to 0.77; short
statements score lower against fact-check titles than long posts do). The feature is built and works; at the
threshold the rule chose it will rarely show.

**The owner's decision, not the rule's.** Lowering `tau_similar` is a one-line config change (`configs/pipeline/dev.yaml`)
trading how often the card appears against how often it points at the wrong fact-check (dev precision is a LOWER
bound; MultiClaim's gold set is incomplete):

| tau_similar | dev coverage of real posts | dev precision | of the 30 hoaxes, cards shown |
| --- | --- | --- | --- |
| 0.86 (the rule) | 4.8% | 0.742 | 1 (the pineapple, already a fast-path verdict) |
| 0.75 | 23.8% | 0.651 | 2 |
| 0.70 | 38.1% | 0.636 | 6 |
| 0.65 | 57.2% | 0.587 | 13 |

A threshold chosen from this table is a product choice made AFTER seeing dev and test numbers, and is recorded as
such if made.

## The owner's decision (2026-10-05): tau_similar = 0.70, and unrated fact-checks are offered too

Shown the table above, the owner chose **0.70** (dev precision 0.636, 38.1% of real posts). This is a PRODUCT decision
made after seeing the dev and test numbers, recorded as post hoc, not a result of the rule (which gave 0.86); setting
`tau_similar: 0.86` in `configs/pipeline/dev.yaml` restores the rule's choice.

**A second change, found by looking at the 30 hoaxes:** `FactCheckMatcher.top1` drops a candidate whose rating cannot be
mapped to a verdict, but several of the best matches are exactly those ("Garlic COVID cure claim crushed by experts", 0.756,
"Bill Gates Did NOT Invent Computer Viruses ...", 0.719). A suggestion makes no verdict, so `FactCheckMatcher.similar` (new,
used only for the suggestion; `top1` and every evaluation path are untouched) offers the best candidate with or without a
rating; with none the card says "{publisher} looked at something similar. This may not be the same message." and does not
claim a rating. The dev curve's precision was measured on the candidates `top1` returned; including unrated ones is a
small, unmeasured extension.

**The 30 typical hoaxes through the real stages (preprocess, claim gate, claim extraction, matcher), 2026-10-05:**
1 fast-path verdict (the pineapple juice), **6 similar fact-check cards** (gargling salt water -> CheckYourFact, rated False;
WhatsApp will start charging -> BOOM, rated False; lemon water cures cancer -> THIP Media, rated False; the Hindi microchip
claim -> AajTak, rated False; garlic cures COVID-19 -> AAP, unrated; "Bill Gates created the coronavirus" -> Lead Stories, unrated,
and that one is about a different Gates claim, which is why the card says "may not be the same message"), 22 "Be careful with
this one" and 1 refused by the claim gate ("Vaccines cause autism"). So 7 of 30 (23%) now get a real source.
