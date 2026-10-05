"""Measure the fact-check finding extractor once (docs/factcheck-finding-protocol.md).

    python scripts/factcheck_finding_check.py collect     # fetch 60 fresh fact-checks, write the sentences for labelling
    python scripts/factcheck_finding_check.py score       # read labels (data/probe/finding_labels.json), apply the two gates

Sample: seed 43, English, Refuted/Supported rating, at most 6 per publisher, disjoint from run 39860deeb1d8's 60.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import canonical_json, sha256_bytes, sha256_file  # noqa: E402
from common.io_jsonl import write_json  # noqa: E402
from common.provenance import env_info, git_info  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from retrieval.live.factcheck_lead import fetch_finding  # noqa: E402

N, PER_PUBLISHER, BAR, SAMPLE_SEED = 60, 6, 0.70, 43
PROTOCOL = ROOT / "docs" / "factcheck-finding-protocol.md"
FIRST_RUN = ROOT / "results" / "39860deeb1d8.json"
COLLECTED = ROOT / "reports" / "factcheck_finding_collected.json"
LABELS = ROOT / "data" / "probe" / "finding_labels.json"


def collect() -> int:
    set_all_seeds(SEED)
    used = {o["id"] for o in json.loads(FIRST_RUN.read_text(encoding="utf-8"))["per_item"]}
    meta = ROOT / "data" / "interim" / "index" / "factcheck_meta.jsonl"
    rows = [json.loads(line) for line in meta.read_text(encoding="utf-8").splitlines() if line.strip()]
    pool = [r for r in rows if r.get("lang") == "en" and r.get("verdict") in ("Refuted", "Supported")
            and (r.get("url") or "").startswith("http") and r["id"] not in used]
    random.Random(SAMPLE_SEED).shuffle(pool)
    chosen, per = [], Counter()
    for r in pool:
        if per[r["publisher"]] < PER_PUBLISHER:
            chosen.append(r)
            per[r["publisher"]] += 1
        if len(chosen) == N:
            break
    cache = ROOT / "data" / "interim" / "live_cache" / "factcheck_finding_measure"
    out = []
    for i, r in enumerate(chosen, 1):
        sentence = fetch_finding(r["url"], r.get("title") or "", cache_dir=cache)
        out.append({"id": r["id"], "publisher": r["publisher"], "url": r["url"], "title": r.get("title"),
                    "rating": r["verdict"], "sentence": sentence})
        print(f"{i:2}/{N} {'ok  ' if sentence else 'FAIL'} {r['publisher']}", flush=True)
    COLLECTED.parent.mkdir(exist_ok=True)
    COLLECTED.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [o for o in out if o["sentence"]]
    print(f"\nextracted {len(ok)} of {len(out)} = {len(ok) / len(out):.3f} (bar {BAR}); sentences in {COLLECTED}")
    return 0


def score() -> int:
    seeded = set_all_seeds(SEED)
    items = json.loads(COLLECTED.read_text(encoding="utf-8"))
    ok = [o for o in items if o["sentence"]]
    coverage = len(ok) / len(items)
    if coverage < BAR:
        # Gate 1 already failed, so the feature is off whatever the sentences say; they are not labelled.
        labels, finding, label_gate = {}, None, False
    else:
        labels = json.loads(LABELS.read_text(encoding="utf-8"))     # {id: true|false}, written by the assistant first
        missing = [o["id"] for o in ok if o["id"] not in labels]
        if missing:
            raise SystemExit(f"unlabelled sentences: {missing}")
        finding = sum(1 for o in ok if labels[o["id"]]) / len(ok) if ok else 0.0
        label_gate = finding >= BAR
    gates = {"coverage": coverage >= BAR, "states_a_finding": label_gate}
    passes = all(gates.values())
    print(json.dumps({"n": len(items), "extracted": len(ok), "coverage": coverage, "states_a_finding": finding,
                      "gates": gates, "passes": passes}, indent=1))
    print("FEATURE SHOWN" if passes else "FEATURE OFF (factcheck_lead: false)")
    cfg = {"experiment": "p9_factcheck_finding", "task": "factcheck_finding", "protocol": "docs/factcheck-finding-protocol.md",
           "n": N, "seed": SAMPLE_SEED, "bar": BAR}
    sha = sha256_file(PROTOCOL)
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + sha256_file(ROOT / "src/retrieval/live/factcheck_lead.py").encode())[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"],
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git": git_info(), "env": env_info(),
        "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": {"n": len(items), "extracted": len(ok), "coverage": coverage, "states_a_finding": finding,
                    "bar": BAR, "gates": gates, "passes": passes},
        "per_item": [{**o, "states_a_finding": labels.get(o["id"])} for o in items]})
    print(f"written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(collect() if sys.argv[1:] == ["collect"] else score() if sys.argv[1:] == ["score"] else 2)
