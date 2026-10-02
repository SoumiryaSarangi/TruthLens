"""Every number the report attributes to a run must be in that run's results file.

    python scripts/check_report_numbers.py docs/report.md

Lesson 11 of the project log: twice the numbers were right and their labels
wrong, because a copied row stayed plausible. Reading a write-up back against
the results by eye is how that slipped through, so this does it mechanically.

Two conventions in the report, both checked:

- inline: a decimal followed (within a few words) by `(run <12-hex hash>)`, e.g.
  "macro-F1 0.2802 (run 164d2289c90b)";
- tables: a row naming exactly one run hash -- every decimal in that row must
  appear in that run's JSON.

"Appears" means some numeric value anywhere in results/<hash>.json -- metrics,
baseline, deltas, calibration -- rounds to the quoted figure at the precision it
is quoted at (sign ignored, so a delta can be written "-0.029" or "0.029 lower").
Exit 1 lists every number it could not find, and every hash with no file.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASH = r"[0-9a-f]{12}"
INLINE = re.compile(rf"(-?\d+\.\d+)[^\d\n|]{{0,60}}?\(run ({HASH})\)")
NUMBER = re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.])")


def leaves(obj) -> list[float]:
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in leaves(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in leaves(x)]
    return []


_cache: dict[str, list[float] | None] = {}


def values(run: str) -> list[float] | None:
    if run not in _cache:
        path = ROOT / "results" / f"{run}.json"
        _cache[run] = (leaves(json.loads(path.read_text(encoding="utf-8")))
                       if path.is_file() else None)
    return _cache[run]


def found(quoted: str, run: str) -> bool:
    decimals = len(quoted.split(".")[1])
    target = abs(float(quoted))
    return any(abs(round(abs(v), decimals) - target) < 10 ** -(decimals + 3)
               for v in values(run) or [])


def check(text: str) -> list[str]:
    problems: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for number, run in INLINE.findall(line):
            if values(run) is None:
                problems.append(f"line {lineno}: run {run} has no results file")
            elif not found(number, run):
                problems.append(f"line {lineno}: {number} is not in run {run}")
        if line.lstrip().startswith("|") and "(run " not in line:
            runs = set(re.findall(rf"(?<![0-9a-f]){HASH}(?![0-9a-f])", line))
            if len(runs) != 1:
                continue
            run = runs.pop()
            if values(run) is None:
                problems.append(f"line {lineno}: run {run} has no results file")
                continue
            cells = [c for c in line.split("|") if run not in c]
            for number in NUMBER.findall("|".join(cells)):
                if not found(number, run):
                    problems.append(f"line {lineno}: {number} is not in run {run} (table row)")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0] if args else "docs/report.md")
    problems = check(path.read_text(encoding="utf-8"))
    for p in problems:
        print(p)
    cited = len(_cache)
    print(f"{path}: {cited} run(s) cited, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
