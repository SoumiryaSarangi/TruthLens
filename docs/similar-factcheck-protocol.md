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
