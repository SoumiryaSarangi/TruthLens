# Split changelog

Every regeneration of a frozen split, and why.

**An entry here means every `results/*.json` produced before it against the
same split is no longer comparable.** That is the cost, and it is why
`scripts/build_splits.py` requires three separate confirmations before it will
overwrite anything.

Entries are appended automatically by `scripts/build_splits.py` when a rewrite
is forced. Do not add one by hand without actually rewriting a split.

## Before adding an entry

Answer this first: is the split wrong, or is the code reading it wrong? It is
almost always the second. CLAUDE.md: "If a split file seems wrong, stop and
ask."

---

_No splits have been regenerated. The first frozen splits are built in
Session 2._
