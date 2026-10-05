# "Which words mattered": faithfulness protocol (pre-registered)

**Status: written 2026-10-05, BEFORE any word influence has been computed, and before the feature exists.** Not changed afterwards
except by dated corrections at the bottom. It decides whether the word view is shown to readers.

## What is being added, and what it is not

An on-demand view on a verdict the system actually gives (the live verdict: two NLI models agreed on Supported or Refuted). It marks
the words of the claim that most pushed the two models toward that verdict, and the source sentence they leaned on. It is an explanation
of **the NLI models' reading of the sources**, not of why a claim is true or false in the world. It never changes a verdict, a
threshold, a confidence or any reported number, and it is not computed unless the reader asks for it.

## The method (fixed here)

For one verdict, take the claim as the models saw it (the English claim for Hindi, Punjabi and Roman input) and the judged passage
with the highest mean P(shown verdict) over the two models (DeBERTa-v3-large, BART-large-MNLI). Split the claim into
whitespace tokens. For each token, remove it and rescore the pair with both models.

- `influence(token) = mean over the two models of [ P(verdict class | full claim) - P(verdict class | claim without the token) ]`.
  Positive: the token pushed toward the verdict. Negative: it pushed against.
- "P(verdict class)" is P(entailment) for a Supported verdict and P(contradiction) for a Refuted one.
- The **top words** are the 3 tokens with the largest influence.
- Source side: the passage's sentences (at most 2, as judged) are removed one at a time the same way; the sentence with the larger
  influence is the one marked. **Reported, not gated** (a two-sentence choice has too few options to gate).

## The question and the data

Is a highlight faithful, i.e. does deleting the words it points to hurt the verdict more than deleting other words?

**Population:** every claim of `fever_fresh` (the 350 fresh English claims, `reports/live_fever/fresh_en.collect.jsonl`,
`fresh_en.scored.jsonl`) for which the shipped rule (V2) gave Supported or Refuted. Inputs are the stored `hypothesis` and judged
`premise` strings, so no new search is made and no claim is chosen after looking at the scores. Claims with fewer than 6 tokens are
excluded (deleting 3 would delete half the claim) and their number is reported. The word view for Hindi and Punjabi runs on the same
English claim the models read, so the English run is the test of the method; the Hindi and Punjabi round trips (`fresh_sub_hi/pa`) are
reported the same way as a secondary table.

## Controls and the rule

For each claim in the population:
- **Top-3 deletion:** delete the 3 highest-influence tokens together; `drop_top = P_before - P_after` (same averaging over two models).
- **Random-3 deletion:** the mean `drop` over 20 random 3-token deletions (numpy seed 42, one generator, claims in file order).
- **Bottom-3 deletion:** delete the 3 lowest-influence tokens; `drop_bottom`.

**The word view ships ONLY IF all of the following hold:**
1. `drop_top > drop_random` on **at least 80%** of the claims;
2. the mean of `drop_top` is **at least 2 times** the mean of `drop_random`;
3. the mean of `drop_bottom` is **no larger** than the mean of `drop_random` (the ranking carries information at both ends, so it is
   not only "long claims lose more when cut").

If any fails the button ships **off**: the code stays, `word_view: false` in the served config, the UI offers nothing, and the log, the
report and this file say that the check failed with the numbers. A pass is reported with the per-claim win rate, both means, and a
bootstrap 95% CI (1000 resamples, seed 42) for the mean difference.

## Honest limits, to be stated in the report

- Occlusion measures sensitivity of two models, and "faithful to the model" is what is tested; it says nothing about the world.
- Deleting words can make an unnatural sentence; the comparison is relative to random deletions, not absolute.
- The top words are chosen by single-word deletion and tested by 3-word deletion on the same pair, so a pass is necessary and not
  sufficient evidence of a useful explanation; the owner's relatives' test (docs/usability-test.md) is the only measure of usefulness.
- The word view exists only for verdicts that exist (about 2% of messages on the fast path, about 30% through the live check). It is not
  offered on an offline guess, which is not a verdict. A fast-path (matched fact-check) word view is NOT part of this protocol and would
  need its own.

## How it is run

`scripts/word_faithfulness.py`, on the CPU (`CUDA_VISIBLE_DEVICES=""`), because the owner's server holds the GPU. It reads the stored
captures and scores the deletions with the two models; the three gate numbers are computed by `word_faithfulness_metrics` in
`src/eval/metrics.py` (no metric inline in the script), and the script writes `results/{config_hash}.json` in the same envelope as
every other run and prints the three gate lines. It runs once on
the committed code; a crash or a refusal may be re-run and is logged with its cause. Nothing is tuned to the outcome.

## Dated corrections

(none yet)
