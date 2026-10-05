# What decides "Be careful with this one": rule fixed before measurement

**Status: written 2026-10-05, and committed together with the rule it measures (`src/manipulation/hoax_cues.py`) BEFORE the
rule has been run on any measurement set.** Not changed afterwards except by dated corrections at the bottom. Approved by the
owner the same day.

## The problem

An unverified message (no matched fact-check, no live verdict, no similar fact-check) is shown as "Be careful with this one" when
the offline model's quiet lean was "Refuted", else as "Hard to say". That lean is a poor signal: it said Refuted to 122 of 125
true claims in the frozen test. So the tone depended on an accident of the model, not on the message: the English "Drinking lemon
juice can cure cancer but hospitals don't reveal this" (lean NEI) got "Hard to say" while the same claim in Roman Hindi (lean
Refuted) got "Be careful".

## The rule being tested (R)

A message is **cautioned** when `caution_cues(claim text, transliteration)` is non-empty. It is the union of:
- **hoax-shape cues** (`hoax_cues`): a cure/kill/prevent word with a health term (miracle_cure); a concealment phrase ("don't reveal",
  "chhupate hain", "big pharma"); "free" with a giveaway noun (giveaway); a charge, ban, block or closure announced as a threat or
  from a deadline (threat_or_charge);
- **pressure techniques** already detected by rule in `manipulation.flags.rule_flags` (time pressure, loaded language,
  authority and popularity appeals, repetition), on the claim's own text.

The card says "Be careful" only for an unverified, cautioned message, before and after the online look-up. Everything else
unverified is "Hard to say". The hidden lean is no longer used for the tone. The rule never changes a verdict, a confidence or any reported number.

## What is measured (all English, all offline, rules only, no model)

| Set | n | Role |
| --- | --- | --- |
| AVeriTeC dev, gold Supported | 122 | **true** claims (real, fact-checked) |
| FEVER fresh, real-world truth T | up to 200 | **true** claims (encyclopedic; an easy set for the rule, reported but weaker evidence) |
| AVeriTeC dev, gold Refuted | 305 | **false** claims (mostly political statements, so recall here is expected to be low) |
| 30 typical WhatsApp hoaxes (`data/probe/hoax30.json`) | 30 | illustrative only: written by me and already seen, so not a gate |
| the current rule (served dev prediction "Refuted") | - | the baseline R must beat on the true sets |

## The gates (R is adopted only if ALL hold; fixed now)

1. **False warnings on true claims:** the share of AVeriTeC dev Supported claims that R cautions is **at most 15%**, with the Wilson
   upper bound reported.
2. **Better than the rule it replaces:** that share is **at most half** the current rule's share on the same claims (the served dev
   prediction is Refuted for them).
3. **It still warns:** R cautions **at least 15%** of AVeriTeC dev Refuted claims (a floor; these are not typical hoaxes) and
   **at least 20 of the 30** typical hoaxes (reported, and a gate because a rule that warns about nothing has not replaced the old one).

**If R fails any gate:** the lean-based wording stays unchanged, the numbers are reported, and the log says so. R is not tuned
after the first run: a change to the cue lists is a new protocol on a fresh set.

## How it is run

`scripts/careful_rule_check.py`, CPU, no model. It writes `results/{config_hash}.json` in the usual envelope (the three gate
numbers come from `eval.metrics.careful_rule_metrics`; no metric is computed inline), and prints PASS or FAIL per gate. Run once.

## Honest limits

- The true sets are not forwards; real true forwards are rare and could not be obtained. The false-warning rate on real forwards
  that happen to be true (a genuine health tip, a real scheme) is unknown and likely higher.
- The cue lists are my own and English-heavy; Hindi, Punjabi and Roman are covered by short lists that were not measured at all
  (no labelled set), only exercised by unit tests and the owner's own examples.
- A cautioned message can still be true. The wording says only that nothing checked it and that messages shaped like this often
  turn out false.

## Dated corrections

(none yet)
