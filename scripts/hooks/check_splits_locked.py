"""Pre-commit hook: a frozen split may not change without its lock changing too.

CLAUDE.md: "NEVER regenerate files in data/splits/. They are frozen and
committed. If a split file seems wrong, stop and ask."

Adding a new split is fine -- that is what Session 2 does. What this blocks is
a split file changing in a commit that does not also update
data/splits/SPLITS.lock, which is how a frozen split quietly drifts and every
number computed against it stops meaning what it says.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LOCK = "data/splits/SPLITS.lock"


def staged_files() -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=False,
    )
    return {line.strip().replace("\\", "/") for line in out.stdout.splitlines() if line.strip()}


def main(argv: list[str]) -> int:
    touched = [Path(a).as_posix() for a in argv if a.endswith(".jsonl")]
    if not touched:
        return 0

    staged = staged_files()
    if LOCK in staged:
        return 0

    print("\nBLOCKED: frozen split file(s) are staged without an updated SPLITS.lock:\n")
    for path in touched:
        print(f"  {path}")
    print(
        f"\n{LOCK} is what proves these files have not drifted. If you genuinely "
        "meant to change a split:\n"
        "  1. work out WHY it changed -- is the split wrong, or the code reading it?\n"
        "  2. record the reason in docs/split-changelog.md\n"
        "  3. run `make lock` and stage the updated lock in this same commit\n"
        "  4. re-run `make leakage`\n\n"
        "Every results/*.json computed against the old split is no longer comparable.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
