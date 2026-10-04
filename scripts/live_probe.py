"""Run the live-search probe set, offline and live, and apply the adoption rule.

    python scripts/live_probe.py                  # set 1 + regression, verdict path, tag "set1"
    python scripts/live_probe.py --probe data/probe/live_probe_2.json --tag set2 --no-regression
    # writes reports/live_probe_<tag>.{json,md}. Set 2 is the validation set for the verdict-path fix; re-running
    # set 1 after the fix is a DIAGNOSTIC of the three known failures, never validation.

For every claim in `data/probe/live_probe.json` plus the eight regression
forwards of `app/static/samples.json`: the served pipeline WITHOUT live search,
then WITH it (the "search live" click). It sends each claim to Wikipedia and,
if a key is configured, Google Fact Check, so it needs the network.

**Scoring and the adoption rule were fixed before the first run** (plan approved
2026-10-04). A demo set of ~40 claims cannot support a metric: results are
reported claim by claim, never as an accuracy.

    outcome of one verdict against its label
      label true         correct: Supported, not abstained   wrong: Refuted, not abstained
      label false        correct: Refuted, not abstained     wrong: Supported, not abstained
      label unverifiable correct: NEI, or abstained          wrong: Supported/Refuted, not abstained
      anything else (Conflicting, abstained, NEI where a verdict was due): undecided

    ADOPT live search only if
      (1) no claim goes from correct offline to wrong live, and
      (2) at least one TRUE claim that was not correct offline is correct live, and
      (3) no unverifiable claim is decided confidently live.
    Otherwise it is reported as tried and not adopted.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def outcome(label: str, verdict: str, abstained: bool) -> str:
    if label == "unverifiable":
        if verdict == "NEI" or abstained:
            return "correct"
        return "wrong" if verdict in ("Supported", "Refuted") else "undecided"
    want, bad = ("Supported", "Refuted") if label == "true" else ("Refuted", "Supported")
    if abstained:
        return "undecided"
    return "correct" if verdict == want else "wrong" if verdict == bad else "undecided"


def adopt(rows: list[dict]) -> dict:
    regressed = [r["id"] for r in rows if r["offline"]["outcome"] == "correct"
                 and r["live"]["outcome"] == "wrong"]
    gained = [r["id"] for r in rows if r["label"] == "true"
              and r["offline"]["outcome"] != "correct" and r["live"]["outcome"] == "correct"]
    unverif_wrong = [r["id"] for r in rows if r["label"] == "unverifiable"
                     and r["live"]["outcome"] == "wrong"]
    return {"regressed": regressed, "gained_true": gained, "unverifiable_decided": unverif_wrong,
            "adopt": not regressed and bool(gained) and not unverif_wrong}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/live_probe.py")
    ap.add_argument("--pause", type=float, default=4.0, help="seconds between claims (rate limits)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--probe", default="data/probe/live_probe.json")
    ap.add_argument("--tag", default="set1")
    ap.add_argument("--no-regression", action="store_true", help="omit the 8 regression forwards")
    ap.add_argument("--translate", action="store_true",
                    help="route A: translate hi/pa claims to English and judge against English Wikipedia")
    ap.add_argument("--evidence-only", action="store_true",
                    help="serve the live path as evidence only (no verdict); default is the verdict path")
    args = ap.parse_args(argv)

    from pipeline.orchestrator import Orchestrator, PipelineConfig

    probe = json.loads((ROOT / args.probe).read_text(encoding="utf-8"))["claims"]
    regression = ([] if args.no_regression else
                  json.loads((ROOT / "app/static/samples.json").read_text(encoding="utf-8"))["regression"])
    items = [{"id": f"reg-{i}", "style": "regression", "label": r["truth"], "text": r["text"]}
             for i, r in enumerate(regression, 1)] + probe
    if args.limit:
        items = items[:args.limit]

    cfg = PipelineConfig.load(ROOT / "configs/pipeline/dev.yaml")
    cfg.stages["generation"] = "template"            # the live path always uses the template
    cfg.live_search = True
    cfg.live_translate = args.translate
    cfg.live_verdict = not args.evidence_only        # the probe judges the VERDICT path by default
    orch = Orchestrator(cfg)
    orch.verify("warm-up")

    rows = []
    for item in items:
        row = {k: item[k] for k in ("id", "style", "label", "text")}
        for mode in ("offline", "live"):
            t0 = time.perf_counter()
            trace = orch.verify(item["text"], live=(mode == "live"))
            res = trace.results[0] if trace.results else None
            row[mode] = {
                "verdict": res.verdict if res else "none", "abstained": res.abstained if res else True,
                "confidence": round(res.confidence, 3) if res else 0.0, "path": res.path if res else "none",
                "sources": res.live_sources if res else [], "seconds": round(time.perf_counter() - t0, 2),
                "passages": [(p.source or "offline", (p.title or p.doc_id)[:60], p.stance)
                             for p in (res.passages[:3] if res else [])],
                "notes": [e.note for e in trace.events if e.stage in ("live", "relevance") and e.note],
            }
            row[mode]["outcome"] = outcome(item["label"], row[mode]["verdict"], row[mode]["abstained"])
        rows.append(row)
        print(f"{row['id']:<8} {item['label']:<12} offline {row['offline']['verdict']:<11}"
              f"{row['offline']['outcome']:<10} live {row['live']['verdict']:<11}{row['live']['outcome']}",
              flush=True)
        time.sleep(args.pause)

    decision = adopt(rows)
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"live_probe_{args.tag}.json").write_text(
        json.dumps({"decision": decision, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["| id | label | offline | live | live sources | live s |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        o, v = r["offline"], r["live"]
        lines.append(f"| {r['id']} | {r['label']} | {o['verdict']}{' (abst.)' if o['abstained'] else ''} "
                     f"{o['confidence']:.2f} [{o['outcome']}] | {v['verdict']}{' (abst.)' if v['abstained'] else ''} "
                     f"{v['confidence']:.2f} [{v['outcome']}] | {', '.join(v['sources']) or '-'} | {v['seconds']} |")
    (out / f"live_probe_{args.tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
