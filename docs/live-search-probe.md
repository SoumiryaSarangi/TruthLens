# Live search: the probe set (post-test Phase 7)

**Written for:** the report's section on live search, and the project owner's decision.

**Status:** two runs, both scored under a rule fixed before they ran. **Neither
adopts a live verdict.** Live search is served as EVIDENCE ONLY (run 2 below).

## What was run

- **Claims:** the 8 regression forwards plus the 32 approved in
  `data/probe/live_probe.json` (17 true, 12 false, 3 unverifiable; English,
  Hindi and Punjabi, native and romanized). The owner checked every label.
- **Each claim twice:** the served pipeline without live search, then with it
  (the "search live" click: Wikipedia and Google Fact Check, key configured).
- **Scoring**, fixed in `scripts/live_probe.py` before the run: for a true
  claim, *correct* is Supported and *wrong* is Refuted; for a false claim the
  reverse; for an unverifiable claim, correct is NEI or abstained. Everything else
  (Conflicting, abstained, NEI where a verdict was due) is undecided.
- **Adoption rule:** adopt only if (1) no correct answer goes wrong, (2) at least
  one true claim becomes correct, and (3) no unverifiable claim is decided
  confidently.

## Result

| | offline (40) | live, both sources up (35) |
| --- | --- | --- |
| correct | 12 | **24** |
| undecided | 10 | 8 |
| wrong | 18 | **3** |

5 of the 40 live runs hit Wikipedia's rate limit (HTTP 429). The pipeline did what
it should: it kept the offline answer and said so in the trace. They are excluded
from the right-hand column and are not counted as live results. The client now
waits at least a second between requests to a host.

- **Rule (2) holds, strongly:** 15 true claims became correct, including the ones
  that started this: **Modi** (not confident → Supported), **Delhi**, **Lahore**,
  **Harmandir Sahib** (Refuted 0.59 → Supported). All three unverifiable claims
  went from a confident "Refuted" to "not enough evidence", which is right.
- **Rule (3) holds:** no unverifiable claim was decided.
- **Rule (1) FAILS:** two claims that were correct offline became wrong live.
- **The Taj Mahal is not fixed:** it is Conflicting, not Supported. Wikipedia
  returns the real article, but the "Black Taj Mahal" legend page and a page about
  Shah Jahan are read as refuting.

## The three failures, all false claims called Supported

| Claim (false) | Live verdict | What it read |
| --- | --- | --- |
| "Lemon water cures cancer" (Hindi) | Supported, 0.49 | Fact-check **headlines** such as "Can lemon water cure cancer? Here is the truth", labelled Supports |
| "The Sun orbits the Earth" (Hindi) | Supported, 0.94 | Wikipedia pages on the Earth's orbit, the Sun and the year, labelled Supports |
| "Chandigarh is Himachal's capital" (Punjabi) | Supported, 0.71 | The Chandigarh and Haryana pages, labelled Supports; the Shimla page, Refutes |

**Cause, one mechanism in three forms:** the NLI model labels a passage that is
*about the same topic* as Supports, even when the passage contradicts the claim or
only restates it as a question. Relevance weighting cannot help, because these
passages are relevant. The weakness is the NLI model reading Hindi and Punjabi.

**What the failures are not:** the verdict model's "forwarded claims are false"
prior (the live path doesn't use it), the relevance gate (these pages passed it
honestly), or rate limiting.

## What this means for the decision

Live search is a large net improvement on this set (12 → 24 correct) and it
fixes the failure that prompted it. It also introduces the worst kind of error for
a misinformation tool: telling someone a falsehood is supported. A single rule
fixed in advance said that outweighs the gain, and it is respected here.

Options, none yet taken:
1. **Evidence only (chosen).** The button shows the relevant Wikipedia and fact-check
   sources and abstains from a verdict. No false "Supported" is possible; the user
   reads the evidence. The ladder's worst case, kept as the safe default.
2. **Fix, then test on fresh claims.** Use the publisher's own rating to set a
   fact-check review's stance (a review rated False refutes its claim; no NLI
   over a headline), and require stronger agreement before the live path may say
   Supported. Any change made after seeing this run must be scored on a NEW probe
   set, never this one, or it is tuned to it.
3. **Leave it off** and document it as future work.

## Per-claim results

| id | truth | offline | live | live sources | live s |
| --- | --- | --- | --- | --- | --- |
| reg-1 | true | Supported (abst.) 0.30 [undecided] | Supported 0.98 [correct] | wikipedia, google_factcheck | 3.38 |
| reg-2 | true | NEI (abst.) 0.32 [undecided] | Supported 0.80 [correct] | wikipedia, google_factcheck | 5.5 |
| reg-3 | true | Refuted 0.57 [wrong] | Conflicting 0.88 [undecided] | wikipedia, google_factcheck | 4.57 |
| reg-4 | true | Supported (abst.) 0.33 [undecided] | Supported 0.85 [correct] | wikipedia, google_factcheck | 4.78 |
| reg-5 | true | Refuted 0.59 [wrong] | Supported 0.82 [correct] | wikipedia, google_factcheck | 2.81 |
| reg-6 | false | Refuted 0.63 [correct] | Refuted 0.83 [correct] | wikipedia, google_factcheck | 2.66 |
| reg-7 | false | Refuted 0.61 [correct] | Supported 0.49 [wrong] | wikipedia, google_factcheck | 2.52 |
| reg-8 | false | Refuted 0.71 [correct] | Refuted 0.71 [correct] (a source was rate-limited: offline answer kept) | - | 19.17 |
| en-t1 | true | Refuted 0.66 [wrong] | Supported 0.62 [correct] | wikipedia, google_factcheck | 2.54 |
| en-t2 | true | Refuted 0.74 [wrong] | NEI 0.78 [undecided] | wikipedia, google_factcheck | 4.82 |
| en-t3 | true | Refuted 0.68 [wrong] | Supported 0.81 [correct] | wikipedia, google_factcheck | 2.67 |
| en-t4 | true | Refuted 0.72 [wrong] | Supported 0.41 [correct] | wikipedia, google_factcheck | 2.81 |
| en-t5 | true | Refuted 0.73 [wrong] | Refuted 0.73 [wrong] (a source was rate-limited: offline answer kept) | - | 17.75 |
| en-t6 | true | Refuted 0.49 [wrong] | Conflicting 0.74 [undecided] | wikipedia, google_factcheck | 4.2 |
| en-t7 | true | Refuted 0.65 [wrong] | NEI 0.74 [undecided] | wikipedia, google_factcheck | 2.61 |
| en-f1 | false | Refuted 0.67 [correct] | NEI 0.90 [undecided] | wikipedia, google_factcheck | 3.84 |
| en-f2 | false | Refuted 0.52 [correct] | Refuted 0.98 [correct] | google_factcheck, wikipedia | 2.76 |
| en-f3 | false | NotAClaim 1.00 [undecided] | NotAClaim 1.00 [undecided] | - | 0.04 |
| en-f4 | false | Refuted 0.68 [correct] | Refuted 0.75 [correct] | wikipedia, google_factcheck | 12.06 |
| en-f5 | false | Refuted 0.66 [correct] | Refuted 0.56 [correct] | wikipedia, google_factcheck | 2.99 |
| en-f6 | false | Refuted 0.79 [correct] | NEI 0.94 [undecided] | wikipedia, google_factcheck | 2.82 |
| hd-t1 | true | Refuted 0.54 [wrong] | Supported 0.58 [correct] | wikipedia, google_factcheck | 2.91 |
| hd-t2 | true | NEI 0.40 [undecided] | Supported 0.81 [correct] | wikipedia, google_factcheck | 5.2 |
| hd-t3 | true | NEI 0.41 [undecided] | Supported 0.93 [correct] | wikipedia, google_factcheck | 13.43 |
| hd-f1 | false | Refuted (abst.) 0.33 [undecided] | Refuted 0.92 [correct] | wikipedia, google_factcheck | 2.84 |
| hd-f2 | false | Refuted 0.47 [correct] | Supported 0.94 [wrong] | wikipedia, google_factcheck | 3.1 |
| hl-t1 | true | Refuted 0.67 [wrong] | Supported 0.74 [correct] | wikipedia, google_factcheck | 4.42 |
| hl-t2 | true | Refuted 0.62 [wrong] | Refuted 0.62 [wrong] (a source was rate-limited: offline answer kept) | - | 17.87 |
| hl-t3 | true | Refuted 0.64 [wrong] | Supported 0.85 [correct] | wikipedia, google_factcheck | 5.14 |
| hl-f1 | false | Refuted 0.56 [correct] | NEI 0.98 [undecided] | wikipedia, google_factcheck | 5.45 |
| hl-f2 | false | Refuted 0.39 [correct] | Refuted 0.80 [correct] | wikipedia, google_factcheck | 2.76 |
| pg-t1 | true | Refuted (abst.) 0.37 [undecided] | Refuted (abst.) 0.37 [undecided] (a source was rate-limited: offline answer kept) | - | 17.66 |
| pg-t2 | true | Refuted 0.52 [wrong] | Supported 0.62 [correct] | wikipedia, google_factcheck | 2.9 |
| pg-t3 | true | NEI (abst.) 0.38 [undecided] | Supported 0.99 [correct] | wikipedia, google_factcheck | 2.76 |
| pg-f1 | false | NEI (abst.) 0.36 [undecided] | Supported 0.71 [wrong] | wikipedia, google_factcheck | 2.87 |
| pl-t1 | true | Refuted 0.61 [wrong] | Supported 0.63 [correct] | wikipedia, google_factcheck | 4.37 |
| pl-f1 | false | Refuted 0.65 [correct] | Refuted 0.65 [correct] (a source was rate-limited: offline answer kept) | - | 17.66 |
| un-1 | unverifiable | Refuted 0.74 [wrong] | NEI 0.85 [correct] | wikipedia, google_factcheck | 2.46 |
| un-2 | unverifiable | Refuted 0.71 [wrong] | NEI (abst.) 0.00 [correct] | wikipedia, google_factcheck | 2.66 |
| un-3 | unverifiable | Refuted 0.75 [wrong] | NEI (abst.) 0.00 [correct] | wikipedia, google_factcheck | 4.89 |

## Run 2: the fix, on a fresh set (2026-10-04): not adopted

**What changed after run 1** (decided from run 1's failures, before set 2 was run):
a fact-check review's stance comes from its publisher's rating rather than NLI
over a headline; NLI reads the two sentences closest to the claim rather than a
whole page; and "Supported" cannot stand over a relevant passage that refutes.
On the three known failures this looked right (diagnostic only: lemon water
Refuted from the fact-checkers' ratings; the Sun/Earth and Chandigarh claims
Conflicting; the Taj Mahal Supported).

**Validation:** `data/probe/live_probe_2.json`, 35 FRESH claims (15 true, 17 false,
3 unverifiable), written and committed before the fix existed, labels approved by
the owner, same scoring, same adoption rule.

| | offline (35) | live verdict path (35) |
| --- | --- | --- |
| correct | 10 | **15** |
| undecided | 13 | 15 |
| wrong | 12 | **5** |

Rule (2) holds (8 true claims became correct), rule (3) holds (no unverifiable
claim was decided). **Rule (1) fails: three correct answers turned wrong**, and
all five live errors are false claims called Supported:

| Claim (false) | Live | What it read |
| --- | --- | --- |
| "Mumbai is the capital of India" | Supported 0.62 | the Mumbai page and a list of state capitals |
| the same, in Punjabi | Supported 0.93 | the Mumbai, Delhi and Nagpur pages |
| "Shimla is the capital of Punjab" (Punjabi) | Supported 0.91 | the Shimla and Chandigarh pages |
| "Gandhi was India's first Prime Minister" (romanized Hindi) | Supported 0.42 | a page about another Gandhi |
| the Hindi "Mumbai" claim | Supported | the Mumbai page |

**Cause:** these claims differ from the truth by ONE entity ("capital of India",
not "of Maharashtra"), and the passages are about the right place. The NLI model
reads the Mumbai page as supporting "Mumbai is a capital" and cannot tell which
capital. The fix removed the failures that came from headlines and from blobs
of text; it cannot remove this one, which is the NLI model's resolution in
Hindi and Punjabi, not a pipeline bug. Rule (1) was written to stop exactly this.

## Decision

**The verdict path is not adopted. Live search is served as evidence only.**
The button lists the relevant Wikipedia pages and fact-check reviews (with each
publisher's own rating) and gives no verdict. That keeps the gain run 1 showed
-- the user sees the Wikipedia page that settles "Modi was Gujarat's chief
minister" -- and makes a false "Supported" impossible. `live_verdict: true`
remains in the code and is OFF.

**What would change this:** an NLI model that resolves single-entity
contradictions in Hindi and Punjabi (a fine-tune, or English NLI over English
Wikipedia pages reached through language links), scored on a third fresh set under
the same rule. Neither fits the time left.

## Per-claim results, run 2

| id | truth | offline | live | live sources |
| --- | --- | --- | --- | --- |
| en-t1 | true | Refuted 0.70 [wrong] | Supported 0.96 [correct] | wikipedia, google_factcheck |
| en-t2 | true | Refuted 0.56 [wrong] | Conflicting 0.96 [undecided] | wikipedia, google_factcheck |
| en-t3 | true | Refuted 0.67 [wrong] | NEI 0.58 [undecided] | wikipedia, google_factcheck |
| en-t4 | true | Refuted 0.73 [wrong] | Conflicting 0.86 [undecided] | wikipedia, google_factcheck |
| en-t5 | true | Refuted 0.77 [wrong] | Conflicting 0.95 [undecided] | wikipedia, google_factcheck |
| en-t6 | true | Refuted 0.59 [wrong] | Supported 0.94 [correct] | wikipedia, google_factcheck |
| en-f1 | false | Refuted 0.65 [correct] | Refuted 0.40 [correct] | wikipedia, google_factcheck |
| en-f2 | false | Refuted 0.71 [correct] | Supported 0.62 [wrong] | wikipedia, google_factcheck |
| en-f3 | false | Refuted 0.75 [correct] | Refuted 0.41 [correct] | wikipedia, google_factcheck |
| en-f4 | false | Refuted 0.53 [correct] | NEI 0.76 [undecided] | wikipedia, google_factcheck |
| en-f5 | false | Refuted 0.68 [correct] | NEI 0.50 [undecided] | wikipedia, google_factcheck |
| en-f6 | false | Refuted 0.72 [correct] | Refuted 0.92 [correct] | wikipedia, google_factcheck |
| hd-t1 | true | NEI 0.39 [undecided] | NEI 0.58 [undecided] | wikipedia, google_factcheck |
| hd-t2 | true | Refuted (abst.) 0.35 [undecided] | Supported 0.62 [correct] | wikipedia, google_factcheck |
| hd-t3 | true | Supported (abst.) 0.37 [undecided] | Supported 0.85 [correct] | wikipedia, google_factcheck |
| hd-f1 | false | Refuted 0.40 [correct] | Conflicting 0.55 [undecided] | wikipedia, google_factcheck |
| hd-f2 | false | NEI (abst.) 0.34 [undecided] | Supported 0.87 [wrong] | wikipedia, google_factcheck |
| hd-f3 | false | Refuted 0.48 [correct] | Conflicting 0.82 [undecided] | wikipedia, google_factcheck |
| hd-f4 | false | NotAClaim 1.00 [undecided] | NotAClaim 1.00 [undecided] | - |
| hl-t1 | true | Refuted 0.58 [wrong] | Conflicting 0.88 [undecided] | wikipedia, google_factcheck |
| hl-t2 | true | Refuted 0.61 [wrong] | NEI 0.70 [undecided] | wikipedia, google_factcheck |
| hl-t3 | true | Refuted (abst.) 0.31 [undecided] | Supported 0.91 [correct] | wikipedia, google_factcheck |
| hl-f1 | false | NEI (abst.) 0.33 [undecided] | NEI (abst.) 0.33 [undecided] (a source was rate-limited) | - |
| hl-f2 | false | none (abst.) 0.00 [undecided] | none (abst.) 0.00 [undecided] | - |
| hl-f3 | false | Refuted 0.65 [correct] | Supported 0.42 [wrong] | wikipedia, google_factcheck |
| pg-t1 | true | Supported (abst.) 0.36 [undecided] | Supported 0.92 [correct] | wikipedia, google_factcheck |
| pg-t2 | true | NEI (abst.) 0.29 [undecided] | Supported 0.83 [correct] | wikipedia, google_factcheck |
| pg-f1 | false | Refuted (abst.) 0.35 [undecided] | Refuted 0.65 [correct] | wikipedia, google_factcheck |
| pg-f2 | false | Refuted 0.39 [correct] | Supported 0.93 [wrong] | wikipedia, google_factcheck |
| pg-f3 | false | Refuted (abst.) 0.38 [undecided] | Supported 0.91 [wrong] | wikipedia, google_factcheck |
| pl-t1 | true | Refuted 0.51 [wrong] | Supported 0.98 [correct] | wikipedia, google_factcheck |
| pl-f1 | false | none (abst.) 0.00 [undecided] | none (abst.) 0.00 [undecided] | - |
| un-1 | unverifiable | Refuted 0.75 [wrong] | NEI 0.99 [correct] | wikipedia, google_factcheck |
| un-2 | unverifiable | Refuted 0.81 [wrong] | NEI (abst.) 0.00 [correct] | wikipedia, google_factcheck |
| un-3 | unverifiable | Refuted 0.57 [wrong] | NEI (abst.) 0.00 [correct] | wikipedia, google_factcheck |

## Run 3: the English route (2026-10-04): the best result yet, still not adopted

**What was built** (route A of the plan approved by the owner): a Hindi/Punjabi claim is
translated to English (NLLB-200 distilled 600M; romanized claims from their
native-script form), English Wikipedia is searched with the English claim and
Hindi/Punjabi pages are swapped for their English counterpart through language
links, and the NLI that reads live evidence is DeBERTa-v3-large
(MNLI/FEVER/ANLI/LingNLI/WANLI) in English, not the multilingual base model.
Config `live_translate`, off in the served config; no existing config hash moves.

**Diagnostics on set 2 (already used, so these CANNOT validate anything).**
Translation alone, with the old NLI: still two false claims Supported (even the
English "Mumbai is the capital of India": the multilingual model called the
Mumbai page entailment at 0.99). Replacing the NLI with the English large model:
that page is contradiction at 0.95, and every set-2 claim was either correct or
undecided (9 true claims gained, none wrong). The English large model was chosen
on those pairs, so set 2 is spent for it too.

**Validation:** `data/probe/live_probe_3.json`, 39 fresh claims, committed before
the route was frozen or run on any of them. Labels pending the owner's approval.
Rule unchanged from sets 1 and 2: adopt only if no correct answer turns wrong, at
least one true claim becomes correct, and no unverifiable claim is decided
confidently. If it fails, live stays evidence-only and route B (fine-tuning on
single-entity contradictions) is the next step.

**Result on set 3** (fresh, 39 claims: 17 true, 19 false, 3 unverifiable; labels approved
by the owner with two "New Delhi" wording fixes, before any run).

*Run 3a* hit Wikipedia's rate limit (HTTP 429) on 12 of 39 claims. In those rows the
card keeps its offline answer by design, so five of its "wrong" outcomes were the
OFFLINE answer, not a live judgement (live 21 correct / 13 undecided / 5 wrong). A 429
is an infrastructure failure, not a metric bug, so the identical set was re-run once
with an 8 s pause between claims. No code, rule or label changed; the first run is
kept in `reports/live_probe_set3_routeA_run1.*`.

*Run 3b* (no source failed on any claim):

| | offline (39) | live, English route (39) |
| --- | --- | --- |
| correct | 12 | **28** |
| undecided | 16 | 9 |
| wrong | 11 | **2** |

Rule (1) holds (no correct answer turned wrong). Rule (2) holds: all 15 true claims
that were not correct offline are correct live, in English, Hindi, romanized Hindi
and Punjabi. **Rule (3) fails**, and that alone rejects the path:

| Claim | Truth | Live | What it read |
| --- | --- | --- | --- |
| "The tea stall near our office closes at 9 pm on Sundays" | unverifiable | Refuted | the Brick Lane Market page ("Refutes") |
| "The Ganges flows into the Arabian Sea", in Hindi | false | **Supported** | the Daman Ganga and Varahi river pages |

Every other false claim was Refuted or left undecided: the single-entity swaps that
rejected the path twice (Chennai/Kerala, Bengaluru/Tamil Nadu, Ambedkar as first
President, Shimla/Punjab) are now Refuted or undecided. Median latency of a live click:
6.2 s (translation and an extra fetch; was about 3 s).

**Why it still fails, and what that says about route B.** Both errors are RELEVANCE
errors, not NLI errors: the NLI model read the wrong page correctly. "Daman Ganga" and
"Varahi" are rivers that do reach the Arabian Sea, and a market page loosely matched a
tea stall. Route B (fine-tuning the NLI on single-entity contradictions) would not fix
either, because the contradictions it teaches are not what failed. What would: an
entity-grounding gate (a passage must be about the claim's subject, not merely a
related page) and a stricter bar before an unverifiable-looking claim can be refuted.
That is a change under test and needs a fourth fresh set.

**Decision: unchanged, live search is served as evidence only.** `live_translate` stays
in the code, off.


## Run 4: the entity-grounding gate (2026-10-04): closer again, still not adopted

**What was built** (frozen and committed before set 4 was run, `86e3098`): on the English
route a Wikipedia page is JUDGED only if its title is about the claim's subject (every
content word of the title matches a claim word by consonant skeleton, so Bangalore and
Bengaluru agree and "Daman Ganga River" does not match "Ganga falls into the Arabian
Sea"); a fact-check review below the fast-path threshold is a verdict on some other
claim, so it is listed and not judged. With no judged page the answer is NEI. A failed
translation keeps the offline answer. Both rules follow from set 3's two errors and
from the project's own tau_match; neither was tuned on set 4.

**Diagnostics on sets 2 and 3 (used, so they validate nothing):** 0 wrong on both
(set 2: 21 correct, set 3: 24 correct, down from 28 because some true claims lose the
page that decided them and become undecided). A first version of the gate, which still
judged fact-check ratings, made two true set-2 claims wrongly Refuted from reviews of
OTHER Modi stories; that is why reviews are not judged below tau_match.

**Validation:** `data/probe/live_probe_4.json`, 38 fresh claims (16 true, 17 false, 5
unverifiable; the owner's review message said 15 / 18, the file and labels are what they
approved), drafted with near-named rivers, a "first Indian to..." trap, spelling-variant
subjects and private claims that use ordinary nouns. Run 4a was again disturbed by
Wikipedia 429s (4 rows kept their offline answer) and was re-run once, identically, with
a 12 s pause; both are kept (`reports/live_probe_set4_gate_run1.*`).

Run 4b (no source failed):

| | offline (38) | live, gated English route (38) |
| --- | --- | --- |
| correct | 8 | **18** |
| undecided | 14 | 19 |
| wrong | 16 | **1** |

Rule (2) holds (10 true claims became correct, in all five scripts) and rule (3) holds
(all five private claims are NEI). **Rule (1) fails on one claim:**

| Claim | Truth | Offline | Live |
| --- | --- | --- | --- |
| "Kalpana Chawla was the first Indian to travel to space" | false | Refuted (correct, by the claim prior) | **Supported**, from the Kalpana Chawla page |

The page says she was the first Indian-born woman in space; the NLI reads that as
supporting "first Indian". That is a genuine reading error on a qualifier (woman, born
in), not a retrieval one, and no gate on titles can see it.

**The price of the gate:** 14 of the 17 false claims are now undecided, not Refuted.
Offline, "Refuted" was often right only because the claim prior says forwards are false
(it also called 16 claims wrong, mostly true ones). The gated route says "no page about
this subject, not sure" instead of guessing; that is safe and low-coverage.

**Across the attempts on fresh sets** the live-wrong count went 5 (set 1,
language-matched), 5 (set 2), 2 (set 3, English route), 1 (set 4, gated), while the
correct count rose. It never reached the pre-fixed bar of zero regressions, and the
remaining error type (a qualifier in a "first ..." claim) needs a better NLI, not a
better gate.

**Decision: unchanged, live search is served as evidence only.** `live_translate` and the
gate stay in the code, off. Further attempts would each need a fresh set; they stop here.
