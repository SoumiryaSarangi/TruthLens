# Why is the live check silent on real claims? Diagnosis protocol (written 2026-10-05, BEFORE any silent claim is read or re-collected)

**Why.** `docs/real-claims-protocol.md` (run `80932a36cbf2`) found that the served live check is right when it speaks but speaks on only 12.2% of AVeriTeC dev claims and 4.0% of the
owner's written claims (about 30% on FEVER). The owner delegated the next decision ("I just need the best results"). Before choosing an improvement, the cause of the silence is
measured by rules fixed here, not guessed from a few memorable examples.

**Frozen.** The served system, the live rule V2 and the test split. This is a diagnosis: nothing is changed by it. A2 stays locked (never diagnosed, never read).

## Data
Every claim of **B (150)** and a **random 100 of the A1 claims that had no shown verdict** (seed 42, after the protocol's A1 split) are sent AGAIN through the owner's running
server (`POST /verify`, `live_search: true`, `include_trace: true`). The full detail is stored in `reports/real_claims/diag_{b,a1}.jsonl` (git-ignored): the claim in English, the
live passages (source, title, retrieval score, stance, stance probability), the similar-fact-check flag, `sources_disagree`, the trace notes and the final verdict, abstained and
confidence. The 6 B claims that were shown in the first run are re-run too, which also measures reproducibility. Sequential, resumable, one retry if a source is degraded.

## Mechanical taxonomy (assigned by code, `scripts/real_claims.py tally`, never by hand; the first matching rule wins)
For every claim with no shown verdict in the diagnosis run:
1. **INFRA**: no response, or a trace note starting "degraded" after the retry.
2. **NO_SOURCE**: no live passage at all (neither Wikipedia nor live fact-check).
3. **NOT_JUDGED**: live passages exist but none carries a stance (the grounding or relevance steps dropped all of them).
4. **SOURCES_DISAGREE**: `sources_disagree` is true.
5. **BOTH_NEI**: judged passages exist and every judged passage's stance is Neutral.
6. **ONE_SIDED**: at least one judged passage is Supports or Refutes, but no verdict was shown (the two models did not agree, or confidence was too low).
7. **OTHER**: anything left. If OTHER exceeds 20% of the silent claims the taxonomy is declared insufficient and revised in a dated correction BEFORE any decision.

Also tallied (descriptive): reproducibility (claims whose shown/silent status differs between the first run and the diagnosis run), silent claims per language and per gold label
(T/F/U), and the number of silent claims that carry a similar-fact-check suggestion.

## Decision rule for the first improvement (fixed now)
After the tally, the first improvement targets the cause category with the largest count among **gold-T and gold-F silent claims** (U claims SHOULD be silent) that has a known fix:
- NO_SOURCE or NOT_JUDGED -> retrieval and query building (search queries, entity handling, translation of Roman and native script).
- BOTH_NEI -> read more of the page (the whole article, not the two nearest sentences).
- ONE_SIDED -> the agreement or qualifier step.
- INFRA -> retries, timeouts and source back-off.
- A category above 35% with no fix is reported as a limit, not worked around.

Only after that are individual claims of A1 and B read (never A2), to choose the concrete change. Any change needs its own pre-registered protocol and is validated on FRESH claims
(A2 once, as the final check; plus new claims if the owner supplies them) against the bars of `docs/real-claims-protocol.md`: precision on shown decidable claims at least 0.85
(Wilson lower bound 0.80) and false-Supported upper bound at most 0.08. **Coverage is the goal, but a change that raises coverage by lowering precision below those bars is rejected.**

## Result
Run `2e34a941d690` (`results/2e34a941d690.json`), 2026-10-05. Collection finished (B 150, A1 100). The taxonomy held: OTHER and INFRA are both 0%.

| Cause of silence | B (142 silent) | of which gold T/F | A1 (100 silent) | of which gold T/F |
| --- | --- | --- | --- | --- |
| NOT_JUDGED (pages found, none passed to the models) | 91 (64%) | 75 | 73 (73%) | 63 |
| BOTH_NEI (judged, nothing settles it) | 43 (30%) | 35 | 26 (26%) | 22 |
| ONE_SIDED (the two models did not agree) | 6 (4%) | 6 | 0 | 0 |
| NO_SOURCE | 2 (1%) | 1 | 1 (1%) | 0 |

- **Reproducibility:** the shown/silent status of a claim differed from the first run for 2 of 150 (B) and 0 of 100 (A1). The silence is stable, not noise.
- **Silent by gold (B):** 25 U (correctly silent), 70 F, 47 T. Silent with a similar-fact-check suggestion: 6 of 142 (B), 24 of 100 (A1).
- **By the decision rule:** the largest category with a known fix is NOT_JUDGED (retrieval, query building and the page-grounding gate). It is above 35%, so the rule asks whether a fix exists.

**What NOT_JUDGED is** (read from A1 and B only, after the tally; the trace notes say so): in 77 of the 91 B cases and 65 of the 73 A1 cases, pages with relevance at least 0.5 WERE found and
then dropped by the grounding gate ("listed, not judged: not a page about the claim's subject"), which needs every content word of a page title to appear in the claim. The rest had no page above 0.5.
The retrieved pages are mostly weakly relevant: the median top relevance of a NOT_JUDGED claim is about 0.57 in B and 0.60 in A1, and the pages are often a different topic from the claim
("Intermittent water supply" for a UPI claim, "Sukanya Samriddhi Account" for a PMJDY claim).

**POST HOC simulation (variants not pre-registered; `scripts/title_gate_simulation.py`, titles only, no model run):** among the 114 gold-T/F silent claims that had a Wikipedia page at least 0.5 relevant,
how many would get a page past a looser gate? Stem matching (Indian~India): 6 in B, 1 in A1. Plus acronyms (UPI~Unified Payments Interface, OTP~One-time password): 23 in B, 2 in A1.
Two-thirds of title words with the head word: 9 and 7. That is at most 23 of 125 gold-T/F B claims (18%) and 2 of 85 in A1 reaching the models, before the models agree or not, and some of
the admitted pairs are plausible but wrong ("Freecharge" for the "PM Free Recharge" scam claim), which is exactly how a false Supported is made.

**Decision (by the rule written above; the owner delegated it):**
1. **No change to the served live check.** A looser gate is a small, unvalidatable and risky lever: at most about 2% of A1 and 15% of B could reach the models, the number that would end as
   correct shown verdicts is a fraction of that, and the held-out data cannot validate such a change (A2 has about 31 shown verdicts in 250; a change affecting about 2% of claims moves about 5 of them).
2. **NOT_JUDGED and BOTH_NEI are reported as LIMITS, not worked around:** the check is silent mainly because Wikipedia and the fact-check search do not hold a page about the claim, or
   hold one that does not settle it. This is a source limit. Real scam-style forwards (a fake "PM Free Recharge" scheme, a made-up bank rule) are exactly what Wikipedia does not cover.
3. The cheapest honest gain is not a model change but the wording: when the check is silent, the card already says nothing settles it and points to a fact-checker; that is the product
   behaving as designed, and it is what the relatives' usability test should now measure.
4. What would need NEW data and its own protocol if the owner wants coverage later: whole-article reading for BOTH_NEI; a larger, newer fact-check index (the live fact-check search
   answers 55 of 61 shown verdicts on AVeriTeC); Roman-script matching for the fast path.
