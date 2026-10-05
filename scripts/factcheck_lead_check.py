"""Measure fact-check lead extraction once (docs/factcheck-lead-protocol.md): 60 fact-checks, seed 42, at most 6 per publisher.

    python scripts/factcheck_lead_check.py
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
from retrieval.live.factcheck_lead import fetch_lead  # noqa: E402

N, PER_PUBLISHER, BAR = 60, 6, 0.70
PROTOCOL = ROOT / "docs" / "factcheck-lead-protocol.md"


def main() -> int:
    seeded = set_all_seeds(SEED)
    meta = ROOT / "data" / "interim" / "index" / "factcheck_meta.jsonl"
    rows = [json.loads(line) for line in meta.read_text(encoding="utf-8").splitlines() if line.strip()]
    pool = [r for r in rows if r.get("lang") == "en" and r.get("verdict") in ("Refuted", "Supported")
            and (r.get("url") or "").startswith("http")]
    random.Random(SEED).shuffle(pool)
    chosen, per = [], Counter()
    for r in pool:
        if per[r["publisher"]] < PER_PUBLISHER:
            chosen.append(r)
            per[r["publisher"]] += 1
        if len(chosen) == N:
            break
    cache = ROOT / "data" / "interim" / "live_cache" / "factcheck_lead_measure"
    out = []
    for i, r in enumerate(chosen, 1):
        lead = fetch_lead(r["url"], r.get("title") or "", cache_dir=cache)
        out.append({"id": r["id"], "publisher": r["publisher"], "url": r["url"], "ok": lead is not None, "lead": lead})
        print(f"{i:2}/{N} {'ok  ' if lead else 'FAIL'} {r['publisher']}", flush=True)
    ok = sum(1 for o in out if o["ok"])
    rate = ok / len(out)
    print(f"\nlead extracted for {ok} of {len(out)} = {rate:.3f} (bar {BAR})")
    print("FEATURE SHOWN" if rate >= BAR else "FEATURE OFF (factcheck_lead: false)")
    for o in [o for o in out if o["ok"]][:10]:
        print(f"  [{o['publisher']}] {o['lead'][:200]}")
    by_pub = {p: [sum(1 for o in out if o["publisher"] == p and o["ok"]), sum(1 for o in out if o["publisher"] == p)] for p in per}
    cfg = {"experiment": "p9_factcheck_lead", "task": "factcheck_lead", "protocol": "docs/factcheck-lead-protocol.md",
           "n": N, "seed": SEED, "bar": BAR}
    sha = sha256_file(PROTOCOL)
    code_sha = sha256_file(ROOT / "src" / "retrieval" / "live" / "factcheck_lead.py")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + code_sha.encode())[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"],
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git": git_info(), "env": env_info(),
        "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": {"n": len(out), "extracted": ok, "rate": rate, "bar": BAR, "passes": rate >= BAR, "by_publisher": by_pub},
        "per_item": out})
    print(f"written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
