"""Run every demo forward through the served pipeline before a demo (UI_UX.md §11).

    python scripts/demo_check.py                         # chips + regression set
    python scripts/demo_check.py --candidates FILE       # try new chip texts

Lesson 13 of the project log, made executable: two real forwards through the
served config have found bugs that thousands of scored rows did not, so after
any change to `configs/pipeline/dev.yaml` the forwards are rerun -- by this,
not by memory.

- **chips** (`app/static/samples.json`): each names the path it exists to show
  (`shows`). If a chip no longer shows it -- the fast path stopped firing, the
  thin-evidence claim stopped abstaining -- this exits 1. UI_UX.md §11: "if one
  breaks, swap the chip, don't improvise."
- **regression**: the seven Phase 5/6 forwards with their truth and the verdict
  last served. A verdict that moves is reported and exits 1; known errors stay
  listed as errors, because the point is to notice change, not to look right.

This prints pipeline outputs; it computes no metric.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SAMPLES = ROOT / "app" / "static" / "samples.json"
CONFIG = ROOT / "configs" / "pipeline" / "dev.yaml"


def shows(kind: str, trace) -> bool:
    """Does this trace show what a chip of this kind is for?"""
    res = trace.results[0] if trace.results else None
    pre = trace.pre
    if kind == "fast_path":
        return res is not None and res.path == "fast"
    if kind == "romanized_hindi":
        return (pre is not None and pre.lang == "hi" and pre.script == "latn"
                and pre.transliterated is not None and res is not None
                and res.verdict != "NotAClaim")
    if kind == "gurmukhi":
        return (pre is not None and pre.lang == "pa" and pre.script == "guru"
                and res is not None and res.verdict != "NotAClaim")
    if kind == "claim_extraction":
        return (res is not None and res.verdict != "NotAClaim"
                and len(res.claim.text) < 0.6 * len(pre.original))
    if kind == "not_a_claim":
        return res is not None and res.verdict == "NotAClaim"
    if kind == "abstained":
        return res is not None and res.abstained
    raise ValueError(f"unknown chip kind {kind!r}")


def describe(text: str, trace, ms: float) -> str:
    pre = trace.pre
    lines = [f"IN  {text[:110]}{'…' if len(text) > 110 else ''}   [{ms:.0f} ms]"]
    if pre is not None:
        lines.append(f"    lang={pre.lang} script={pre.script} "
                     f"translit={'yes' if pre.transliterated else 'no'}")
    for r in trace.results:
        lines.append(f"    claim: {r.claim.text[:100]}")
        line = (f"    path={r.path} verdict={r.verdict} conf={r.confidence:.3f} "
                f"abstained={r.abstained} explanation={r.explanation_source}")
        if r.match is not None:
            line += f"\n    match={r.match.score:.3f} {r.match.publisher}: {r.match.title[:80]}"
        if r.manipulation_flags:
            line += f"\n    flags={r.manipulation_flags}"
        lines.append(line)
        for p in r.passages[:3]:
            lines.append(f"      [{p.stance}] {(p.title or p.doc_id)[:70]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/demo_check.py")
    ap.add_argument("--candidates", help="a text file, one candidate forward per line")
    ap.add_argument("--config", default=str(CONFIG))
    args = ap.parse_args(argv)

    from pipeline.orchestrator import Orchestrator, PipelineConfig

    orch = Orchestrator(PipelineConfig.load(args.config))
    orch.verify("warm-up")                       # load every model before timing

    if args.candidates:
        for text in Path(args.candidates).read_text(encoding="utf-8").splitlines():
            if text.strip():
                t0 = time.perf_counter()
                trace = orch.verify(text)
                print(describe(text, trace, (time.perf_counter() - t0) * 1000), flush=True)
        return 0

    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    failures: list[str] = []
    print("== chips")
    for chip in samples["chips"]:
        t0 = time.perf_counter()
        trace = orch.verify(chip["text"])
        ms = (time.perf_counter() - t0) * 1000
        ok = shows(chip["shows"], trace)
        print(f"[{'ok' if ok else 'BROKEN'}] {chip['label']} -> {chip['shows']}")
        print(describe(chip["text"], trace, ms), flush=True)
        if not ok:
            failures.append(f"chip {chip['label']!r} no longer shows {chip['shows']}")

    print("\n== regression")
    for row in samples.get("regression", []):
        t0 = time.perf_counter()
        trace = orch.verify(row["text"])
        ms = (time.perf_counter() - t0) * 1000
        res = trace.results[0] if trace.results else None
        served = ("abstained:" + res.verdict) if res and res.abstained else (
            res.verdict if res else "none")
        moved = served != row["served"]
        print(f"[{'MOVED' if moved else 'same'}] truth={row['truth']} "
              f"served={served} (last {row['served']})")
        print(describe(row["text"], trace, ms), flush=True)
        if moved:
            failures.append(f"{row['text'][:40]!r}: {row['served']} -> {served}")

    print()
    for f in failures:
        print(f"FAIL {f}")
    print("OK: every chip shows its path and no regression verdict moved"
          if not failures else f"{len(failures)} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
