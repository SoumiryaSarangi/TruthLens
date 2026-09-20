---
description: Run the eval harness on a config and report the numbers against the baseline
---

Run `make eval CONFIG=$ARGUMENTS`.

Then report, briefly:

1. The headline metric and the baseline it beat (or did not beat).
2. Every per-language and per-script cell, flagging which are `low_n`.
3. Every entry in the results JSON's `warnings` array, verbatim. Do not
   summarise a warning away -- a `SUSPICIOUSLY HIGH` warning is the most
   important line in the file.
4. The `config_hash`, so the run can be referenced later.

If the harness REFUSED the run, do not work around the refusal. Report what it
refused and why, and ask before changing anything. The guardrails exist
because a plausible wrong number is worse than no number.
