"""The live check on real claims (docs/real-claims-protocol.md, pre-registered).

    python scripts/real_claims.py collect --set a          # RC-A: 500 AVeriTeC dev claims through the running server
    python scripts/real_claims.py collect --set b          # RC-B: the owner's 120 plain claims (data/private/real_forwards.csv)
    python scripts/real_claims.py collect --set d          # RC-D: 40 claims x 3 renderings (English, Roman, native script), real_forwards_triplets.csv
    python scripts/real_claims.py report                   # metrics, results/<hash>.json; errors are printed from A1 and B only

The collector calls the owner's running server (`POST /verify`, `live_search: true`), so it measures exactly the
served system and needs no second GPU process. Sequential and resumable. A claim whose response notes a degraded
source (HTTP 429 and the like) is re-run ONCE and both runs are kept.

RC-A is split once by seed 42: the first 250 shuffled uids are A1 (explore: failure cases may be read), the last 250
are A2 (locked: per-claim results are stored but no A2 error is printed by this script).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "reports" / "real_claims"
SERVER = "http://127.0.0.1:8000"
SEED = 42
GOLD = {"Supported": "T", "Refuted": "F", "Not Enough Evidence": "U", "NEI": "U", "Conflicting": "U",
        "Conflicting Evidence/Cherrypicking": "U"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def rca_claims() -> list[dict]:
    gold = {r["uid"]: r["label"] for r in read_jsonl(ROOT / "data" / "splits" / "averitec" / "dev.jsonl")}
    text = {r["uid"]: r["text"] for r in read_jsonl(ROOT / "data" / "interim" / "averitec" / "dev.jsonl")}
    uids = sorted(gold)
    random.Random(SEED).shuffle(uids)
    return [{"uid": u, "text": text[u], "gold": GOLD[gold[u]], "part": "A1" if i < 250 else "A2"} for i, u in enumerate(uids)]


# RC-D rows whose text states its own verdict, so the label can be read either way: dropped before the run
# (docs/real-claims-protocol.md, correction 3).
RCD_EXCLUDED = {8, 9, 14, 15, 68, 83}


def rcb_claims(name: str = "real_forwards.csv", prefix: str = "rcb", part: str = "B") -> list[dict]:
    path = ROOT / "data" / "private" / name
    if not path.exists():
        raise SystemExit(f"{path} does not exist: the owner's claims go there (see real_forwards_TEMPLATE.csv)")
    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            label = (r.get("label") or "").strip().upper()
            if r.get("text", "").strip() and label in ("T", "F", "U"):
                rec = {"uid": f"{prefix}:{r['id']}", "text": r["text"].strip(), "gold": label, "part": part}
                if part == "B":
                    rec["lang"] = r.get("language", "")
                    rec["family"] = (r.get("source_for_label") or "").strip()
                if part == "D":
                    if int(r["id"]) in RCD_EXCLUDED:
                        continue
                    rec["lang"] = r.get("language", "")
                    rec["cluster"] = (int(r["id"]) - 1) // 3
                out.append(rec)
    return out


def post(text: str) -> dict:
    req = urllib.request.Request(f"{SERVER}/verify", data=json.dumps({"text": text, "include_trace": True, "live_search": True}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)


def summarise(body: dict) -> dict:
    r = (body.get("results") or [{}])[0]
    notes = [e.get("note") or "" for e in (body.get("trace") or {}).get("events", [])]
    live = r.get("live_sources") or []
    shown = r.get("verdict") in ("Supported", "Refuted") and not r.get("abstained") and (bool(live) or r.get("path") == "fast")
    decider = None
    if shown:
        decider = "factcheck" if (r.get("path") == "fast" or r.get("match")) else "wikipedia"
    return {"checkworthy": body.get("checkworthy"), "path": r.get("path"), "verdict": r.get("verdict"), "abstained": r.get("abstained"),
            "confidence": r.get("confidence"), "live_sources": live, "shown": r.get("verdict") if shown else None, "decider": decider,
            "sources_disagree": r.get("sources_disagree"), "degraded": any(n.startswith("degraded") or "degraded" in n for n in notes)}


def collect(which: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    claims = (rca_claims() if which == "a" else rcb_claims() if which == "b"
              else rcb_claims("real_forwards_triplets.csv", "rcd", "D"))
    path = OUT / f"rc{which}.collect.jsonl"
    done = {r["uid"] for r in read_jsonl(path)}
    print(f"RC-{which.upper()}: {len(claims)} claims, {len(done)} already done", flush=True)
    t0 = time.time()
    for i, c in enumerate(claims, 1):
        if c["uid"] in done:
            continue
        runs = []
        for attempt in (1, 2):
            try:
                s = summarise(post(c["text"]))
            except Exception as exc:  # the server was busy or a source failed: one more try, then keep the failure
                s = {"error": f"{type(exc).__name__}: {exc}"[:200], "degraded": True, "shown": None, "decider": None}
            s["attempt"] = attempt
            runs.append(s)
            if not s.get("degraded"):
                break
            time.sleep(8)
        rec = {**c, "runs": runs, "final": runs[-1], "seconds": round(time.time() - t0, 1)}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  {i}/{len(claims)} {c['part']} gold={c['gold']} shown={rec['final'].get('shown')} decider={rec['final'].get('decider')}", flush=True)
    return 0


def report() -> int:
    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds
    from eval.metrics import real_claims_metrics

    seeded = set_all_seeds(SEED)
    a, b, d = (read_jsonl(OUT / f"rc{k}.collect.jsonl") for k in "abd")
    pick = lambda rs: [{"gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider")} for r in rs]  # noqa: E731
    sets = {"A1": [r for r in a if r["part"] == "A1"], "A2": [r for r in a if r["part"] == "A2"], "A": a, "B": b, "D": d}
    metrics = {k: real_claims_metrics(pick(v)) for k, v in sets.items() if v}
    errors = {k: [{"uid": r["uid"], "gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider"), "text": r["text"]}
                  for r in sets[k] if r["final"].get("shown") and (r["final"]["shown"] == "Supported") != (r["gold"] == "T") and r["gold"] in ("T", "F")]
              for k in ("A1", "B", "D") if sets.get(k)}
    if b:
        from eval.metrics import cluster_rates_ci, transfer_verdict_with_clusters
        fams = {f: i for i, f in enumerate(sorted({r["family"] for r in b}))}
        brows = [{"cluster": fams[r["family"]], "gold": r["gold"], "shown": r["final"].get("shown")} for r in b]
        rates = cluster_rates_ci(brows)
        metrics["B"]["cluster_rates"] = rates
        metrics["B"]["transfers_conservative"] = transfer_verdict_with_clusters(metrics["B"]["transfers"], rates)
        print("RC-B by source family:", json.dumps(rates), "->", metrics["B"]["transfers_conservative"])
    for k, m in metrics.items():
        al = m["all"]
        print(f"{k}: n={al['n']} shown={al['shown']} coverage={al['coverage']:.3f} precision={al['precision']} "
              f"false_supported={al['false_supported']}/{al['gold_false']} -> {m['transfers']}")
    for k, errs in errors.items():
        print(f"\n{k} wrong answers ({len(errs)}):")
        for e in errs:
            print(f"  [{e['gold']} but {e['shown']} via {e['decider']}] {e['text'][:140]}")
    triplets = None
    if d:
        from eval.metrics import cluster_consistency, cluster_rates_ci
        trows = [{"cluster": r["cluster"], "lang": r["lang"], "gold": r["gold"], "shown": r["final"].get("shown")} for r in d]
        triplets = {"consistency": cluster_consistency(trows), "rates_cluster_bootstrap95": cluster_rates_ci(trows),
                    "by_language": {lg: real_claims_metrics([{"gold": t["gold"], "shown": t["shown"], "decider": None}
                                                             for t in trows if t["lang"] == lg])["all"] for lg in sorted({t["lang"] for t in trows})}}
        print(chr(10) + "RC-D (40 claims x 3 renderings):", json.dumps(triplets["consistency"]), "cluster bootstrap:", json.dumps(triplets["rates_cluster_bootstrap95"]))
        for lg, m in triplets["by_language"].items():
            print(f"  {lg}: n={m['n']} shown={m['shown']} coverage={m['coverage']:.3f} precision={m['precision']}")
    cfg = {"experiment": "p9_real_claims", "task": "real_claims", "protocol": "docs/real-claims-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "real-claims-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + str(sum(len(v) for v in sets.values())).encode())[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": metrics, "rcd_triplets": triplets, "errors_A1_B_D": errors})
    print(f"\nwritten results/{h}.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--set", choices=("a", "b", "d"), required=True)
    sub.add_parser("report")
    args = ap.parse_args()
    return collect(args.set) if args.cmd == "collect" else report()


if __name__ == "__main__":
    raise SystemExit(main())
