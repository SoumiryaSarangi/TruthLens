---
description: Build an ablation table from existing results, native vs romanized
---

Build an ablation table for: $ARGUMENTS

Rules:

- Use only numbers already in `results/*.json`. If a cell needs a run that
  does not exist, leave it blank and list the configs that would fill it --
  do not estimate, interpolate, or reuse a number from a different split.
- Every row carries its dumb baseline in the same table. A row without a
  baseline is not a result.
- Report native and romanized as separate columns with the gap between them.
  The gap is the finding.
- Mark every cell whose `n` is below `min_cell_n`. Punjabi cells will be
  small; say so rather than letting the number stand unqualified.
- Quote each `config_hash` so every number is traceable.

`make table` regenerates `docs/results.md`; start from that rather than
re-reading every JSON by hand.
