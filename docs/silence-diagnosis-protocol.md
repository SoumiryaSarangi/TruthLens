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
(to be filled after the run)
