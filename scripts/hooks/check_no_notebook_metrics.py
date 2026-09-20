"""Pre-commit hook: no metric may be computed inside a notebook.

CLAUDE.md: "No metric is ever computed inline in a notebook. Only via
src/eval/evaluate.py."

docs/build-plan.md puts it as "notebooks/ -- plots only, never logic". The
failure mode this prevents is a number in the report that came from a cell
nobody can re-run, computed with a slightly different averaging rule than the
harness uses.

Reading results/*.json in a notebook and plotting it is fine and expected.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Metric computation. Deliberately narrow: these are the calls that produce a
# number that could end up in the report.
BANNED = [
    (re.compile(r"\bfrom\s+sklearn\.metrics\s+import\b"), "sklearn.metrics import"),
    (re.compile(r"\bsklearn\.metrics\."), "sklearn.metrics call"),
    (re.compile(r"\b(f1_score|precision_score|recall_score|accuracy_score|"
                r"classification_report|roc_auc_score|confusion_matrix)\s*\("),
     "a scikit-learn metric call"),
    (re.compile(r"\b(ndcg_score|average_precision_score)\s*\("), "a ranking metric call"),
]

ALLOW_MARKER = "# eval-harness-exempt"


def check(path: Path) -> list[str]:
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: could not parse notebook ({exc})"]

    problems: list[str] = []
    for i, cell in enumerate(nb.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if ALLOW_MARKER in source:
            continue
        for pattern, label in BANNED:
            if pattern.search(source):
                problems.append(f"{path}: cell {i} contains {label}")
                break
    return problems


def main(argv: list[str]) -> int:
    problems: list[str] = []
    for arg in argv:
        problems.extend(check(Path(arg)))
    if not problems:
        return 0

    print("\nBLOCKED: metrics computed inside a notebook:\n")
    for problem in problems:
        print(f"  {problem}")
    print(
        "\nCLAUDE.md: metrics exist in exactly one place, src/eval/evaluate.py.\n"
        "Write the predictions to a JSONL, add a config, run `make eval`, and load\n"
        "results/<hash>.json in the notebook to plot it.\n"
        f"If a cell genuinely needs an exception, mark it with {ALLOW_MARKER}.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
