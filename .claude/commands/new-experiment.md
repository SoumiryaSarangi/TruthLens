---
description: Propose a new experiment as a config plus a minimal diff, after the three questions
---

I want to add: $ARGUMENTS

Before proposing any code, answer the three questions from
docs/build-plan.md. Do not skip the third.

1. **What is the current number for this component?** Read `results/*.json`
   (or `docs/results.md`) and quote the config_hash and the metric. If no run
   exists, say so plainly.
2. **What is the dumb baseline?** Name a baseline registered in
   `src/eval/baselines.py`, or say what new one is needed and why.
3. **What would make this experiment invalid?** Be concrete and specific to
   this change: which split could leak, which metric could be averaged the
   wrong way, which cell is too small to support the claim.

Then propose:

- a new `configs/<name>.yaml`, and
- the smallest code diff that produces a predictions JSONL,

in that order. No metric code outside `src/eval/`. No touching
`data/splits/`. Stop and wait for approval before writing anything.
