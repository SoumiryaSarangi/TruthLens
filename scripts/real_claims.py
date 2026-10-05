"""The live check on real claims (docs/real-claims-protocol.md, pre-registered).

    python scripts/real_claims.py collect --set a          # RC-A: 500 AVeriTeC dev claims through the running server
    python scripts/real_claims.py collect --set b          # RC-B: the owner's 120 plain claims (data/private/real_forwards.csv)
    python scripts/real_claims.py collect --set c          # RC-C: the same 120 claims as chatty forwards with the correction inside (real_forwards_chatty.csv)
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


def rcb_claims(name: str = "real_forwards.csv", prefix: str = "rcb", part: str = "B") -> list[dict]:
    path = ROOT / "data" / "private" / name
    if not path.exists():
        raise SystemExit(f"{path} does not exist: the owner's claims go there (see real_forwards_TEMPLATE.csv)")
    out = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            label = (r.get("label") or "").strip().upper()
            if r.get("text", "").strip() and label in ("T", "F", "U"):
                out.append({"uid": f"{prefix}:{r['id']}", "text": r["text"].strip(), "gold": label, "part": part})
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
              else rcb_claims("real_forwards_chatty.csv", "rcc", "C"))
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
    a, b, c = (read_jsonl(OUT / f"rc{k}.collect.jsonl") for k in "abc")
    pick = lambda rs: [{"gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider")} for r in rs]  # noqa: E731
    sets = {"A1": [r for r in a if r["part"] == "A1"], "A2": [r for r in a if r["part"] == "A2"], "A": a, "B": b, "C": c}
    metrics = {k: real_claims_metrics(pick(v)) for k, v in sets.items() if v}
    errors = {k: [{"uid": r["uid"], "gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider"), "text": r["text"]}
                  for r in sets[k] if r["final"].get("shown") and (r["final"]["shown"] == "Supported") != (r["gold"] == "T") and r["gold"] in ("T", "F")]
              for k in ("A1", "B", "C") if sets.get(k)}
    for k, m in metrics.items():
        al = m["all"]
        print(f"{k}: n={al['n']} shown={al['shown']} coverage={al['coverage']:.3f} precision={al['precision']} "
              f"false_supported={al['false_supported']}/{al['gold_false']} -> {m['transfers']}")
    for k, errs in errors.items():
        print(f"\n{k} wrong answers ({len(errs)}):")
        for e in errs:
            print(f"  [{e['gold']} but {e['shown']} via {e['decider']}] {e['text'][:140]}")
    paired = None
    if b and c:
        from eval.metrics import paired_flip_counts
        paired = paired_flip_counts({r["uid"].split(":")[1]: (r["gold"], r["final"].get("shown")) for r in b},
                                    {r["uid"].split(":")[1]: (r["gold"], r["final"].get("shown")) for r in c})
        print("\nB (plain) vs C (chatty), same 120 claims:", json.dumps(paired))
    cfg = {"experiment": "p9_real_claims", "task": "real_claims", "protocol": "docs/real-claims-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "real-claims-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + str(sum(len(v) for v in sets.values())).encode())[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": metrics, "paired_B_vs_C": paired, "errors_A1_B_C": errors})
    print(f"\nwritten results/{h}.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--set", choices=("a", "b"), required=True)
    sub.add_parser("report")
    args = ap.parse_args()
    return collect(args.set) if args.cmd == "collect" else report()


if __name__ == "__main__":
    raise SystemExit(main())
