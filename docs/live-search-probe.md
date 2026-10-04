# Live search: the probe set (post-test Phase 7)

**Written for:** the report's section on live search, and the project owner's decision.

**Status:** run 1 of the probe set, scored under a rule fixed before it ran.
**Result: NOT adopted.** The live path is built, tested and switched off
(`live_search: false` in `configs/pipeline/dev.yaml`).

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
1. **Evidence only.** The button shows the relevant Wikipedia and fact-check
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
