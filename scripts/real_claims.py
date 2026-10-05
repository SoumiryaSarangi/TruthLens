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


# RC-E rows (the owner's 100 new claims) whose text states that the evidence is limited or unsettled, so the U label can be
# read from the text itself: rows 86-100, dropped before any run (docs/live-retrieval-v2-protocol.md, correction 1).
RCE_EXCLUDED = set(range(86, 101))


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
                if part == "E":
                    if int(r["id"]) in RCE_EXCLUDED:
                        continue
                    urls = [w for w in (r.get("source_for_label") or "").split() if w.startswith("http")]
                    rec["family"] = urls[0] if urls else (r.get("source_for_label") or "").strip()
                if part == "D":
                    if int(r["id"]) in RCD_EXCLUDED:
                        continue
                    rec["lang"] = r.get("language", "")
                    rec["cluster"] = (int(r["id"]) - 1) // 3
                out.append(rec)
    return out


def rcf_claims(name: str = "rcf_claims.csv", prefix: str = "rcf", part: str = "F") -> list[dict]:
    """RC-F and RC-G (docs/polarity-guard-protocol.md, docs/polarity-guard-v2-protocol.md): the owner's paraphrases and negations of real
    fact-checked claims, in long form."""
    path = ROOT / "data" / "private" / name
    if not path.exists():
        raise SystemExit(f"{path} does not exist (see docs/polarity-guard-protocol.md)")
    with path.open(encoding="utf-8", newline="") as f:
        return [{"uid": f"{prefix}:{r['id']}", "text": r["text"].strip(), "gold": r["gold"], "part": part, "kind": r["kind"],
                 "source_id": int(r["source_id"]), "lang": r["language"], "verbatim": r["verbatim_copy"] == "1"} for r in csv.DictReader(f)]


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


def collect(which: str, suffix: str = "", only: str | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    claims = (rca_claims() if which == "a" else rcb_claims() if which == "b"
              else rcb_claims("real_forwards_new.csv", "rce", "E") if which == "e"
              else rcb_claims("real_forwards_triplets.csv", "rcd", "D"))
    if only:
        claims = [c for c in claims if c["part"] == only]
    path = OUT / f"rc{which}{suffix}.collect.jsonl"
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
    a, b, d, e = (read_jsonl(OUT / f"rc{k}.collect.jsonl") for k in "abde")
    pick = lambda rs: [{"gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider")} for r in rs]  # noqa: E731
    sets = {"A1": [r for r in a if r["part"] == "A1"], "A2": [r for r in a if r["part"] == "A2"], "A": a, "B": b, "D": d, "E": e}
    metrics = {k: real_claims_metrics(pick(v)) for k, v in sets.items() if v}
    errors = {k: [{"uid": r["uid"], "gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider"), "text": r["text"]}
                  for r in sets[k] if r["final"].get("shown") and (r["final"]["shown"] == "Supported") != (r["gold"] == "T") and r["gold"] in ("T", "F")]
              for k in ("A1", "B", "D") if sets.get(k)}
    for key, rs in (("B", b), ("E", e)):
        if not rs:
            continue
        from eval.metrics import cluster_rates_ci, transfer_verdict_with_clusters
        fams = {f: i for i, f in enumerate(sorted({r["family"] for r in rs}))}
        brows = [{"cluster": fams[r["family"]], "gold": r["gold"], "shown": r["final"].get("shown")} for r in rs]
        rates = cluster_rates_ci(brows)
        metrics[key]["cluster_rates"] = rates
        metrics[key]["transfers_conservative"] = transfer_verdict_with_clusters(metrics[key]["transfers"], rates)
        print(f"RC-{key} by source family:", json.dumps(rates), "->", metrics[key]["transfers_conservative"])
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


def _diag_claims(which: str) -> list[dict]:
    """B (all 150) or the 100 random A1 claims that were silent in the first run (docs/silence-diagnosis-protocol.md)."""
    if which == "b":
        return rcb_claims()
    if which == "f":
        return rcf_claims()
    if which == "g":
        return rcf_claims("rcg_claims.csv", "rcg", "G")
    if which == "e":      # only the English translation is wanted from this run (offline fact-check scoring); RC-E errors stay unread
        return rcb_claims("real_forwards_new.csv", "rce", "E")
    first = {r["uid"]: r for r in read_jsonl(OUT / "rca.collect.jsonl")}
    silent = [c for c in rca_claims() if c["part"] == "A1" and first.get(c["uid"], {}).get("final", {}).get("shown") is None]
    random.Random(SEED).shuffle(silent)
    return silent[:100]


def detail(body: dict) -> dict:
    r = (body.get("results") or [{}])[0]
    notes = [e.get("note") or "" for e in (body.get("trace") or {}).get("events", []) if e.get("note")]
    return {"claim_en": r.get("claim_en"), "path": r.get("path"), "verdict": r.get("verdict"), "abstained": r.get("abstained"),
            "confidence": r.get("confidence"), "live_sources": r.get("live_sources") or [], "sources_disagree": r.get("sources_disagree"),
            "similar": bool(r.get("similar_match")), "match": bool(r.get("match")), "notes": notes,
            "passages": [{"source": p.get("source"), "title": p.get("title"), "retrieval": p.get("retrieval_score"), "stance": p.get("stance"),
                          "stance_prob": p.get("stance_prob")} for p in (r.get("passages") or [])]}


def diagnose(which: str, suffix: str = "") -> int:
    claims = _diag_claims(which)
    path = OUT / f"diag_{which}{suffix}.jsonl"
    done = {r["uid"] for r in read_jsonl(path)}
    print(f"diagnose {which}: {len(claims)} claims, {len(done)} done", flush=True)
    for i, c in enumerate(claims, 1):
        if c["uid"] in done:
            continue
        d = None
        for _attempt in (1, 2):
            try:
                d = detail(post(c["text"]))
            except Exception as exc:
                d = {"error": f"{type(exc).__name__}: {exc}"[:200], "notes": ["degraded: error"], "passages": []}
            if not any(n.startswith("degraded") for n in d["notes"]):
                break
            time.sleep(8)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**c, "diag": d}, ensure_ascii=False) + "\n")
        print(f"  {i}/{len(claims)} gold={c['gold']}", flush=True)
    return 0


def category(d: dict) -> str:
    """The mechanical taxonomy of docs/silence-diagnosis-protocol.md; the first matching rule wins."""
    if d.get("error") or any(n.startswith("degraded") for n in d.get("notes", [])):
        return "INFRA"
    live = [p for p in (d.get("passages") or []) if p.get("source") in ("wikipedia", "factcheck_live")]
    if not live:
        return "NO_SOURCE"
    judged = [p for p in live if p.get("stance")]
    if not judged:
        return "NOT_JUDGED"
    if d.get("sources_disagree"):
        return "SOURCES_DISAGREE"
    if all(p["stance"] == "Neutral" for p in judged):
        return "BOTH_NEI"
    if any(p["stance"] in ("Supports", "Refutes") for p in judged):
        return "ONE_SIDED"
    return "OTHER"


def _is_shown(d: dict) -> bool:
    return d.get("verdict") in ("Supported", "Refuted") and not d.get("abstained") and (bool(d.get("live_sources")) or d.get("path") == "fast")


def tally() -> int:
    import collections

    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds

    seeded = set_all_seeds(SEED)
    summary: dict = {}
    for which in ("b", "a1"):
        rows = read_jsonl(OUT / f"diag_{which}.jsonl")
        if not rows:
            continue
        first = {r["uid"]: r for r in read_jsonl(OUT / ("rcb.collect.jsonl" if which == "b" else "rca.collect.jsonl"))}
        silent = [r for r in rows if not _is_shown(r["diag"])]
        print(f"\n== {which.upper()}: {len(rows)} re-run, {len(silent)} silent in the diagnosis run")
        cats = collections.Counter(category(r["diag"]) for r in silent)
        for k, v in cats.most_common():
            dec = sum(1 for r in silent if category(r["diag"]) == k and r["gold"] in ("T", "F"))
            print(f"  {k:17s} {v:4d} ({v / len(silent):.0%})   of which gold T/F: {dec}")
        flips = sum(1 for r in rows if (first[r["uid"]]["final"].get("shown") is not None) != _is_shown(r["diag"]))
        print(f"  shown/silent status differs from the first run: {flips} of {len(rows)}")
        print("  by gold:", dict(collections.Counter(r["gold"] for r in silent)))
        if which == "b":
            print("  by language:", dict(collections.Counter(r.get("lang") for r in silent)))
        print("  silent with a similar-fact-check suggestion:", sum(1 for r in silent if r["diag"].get("similar")))
        summary[which] = {"rerun": len(rows), "silent": len(silent), "categories": dict(cats),
                          "categories_gold_t_or_f": {k: sum(1 for r in silent if category(r["diag"]) == k and r["gold"] in ("T", "F")) for k in cats},
                          "status_differs_from_first_run": flips, "silent_by_gold": dict(collections.Counter(r["gold"] for r in silent)),
                          "silent_with_similar_suggestion": sum(1 for r in silent if r["diag"].get("similar"))}
    cfg = {"experiment": "p9_silence_diagnosis", "task": "silence_diagnosis", "protocol": "docs/silence-diagnosis-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "silence-diagnosis-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + canonical_json(summary))[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": summary})
    print(f"\nwritten results/{h}.json")
    return 0


def confirm() -> int:
    """The served-system confirmation of Stage 4 (docs/live-retrieval-v2-protocol.md): A2 + RC-E through the restarted server at
    tau_live_match 0.70, against the offline projection of run 6ff18b9f8dfc and the pooled bars. Run once."""
    import factcheck_match_curve as fm
    from eval.metrics import wilson_interval

    served = []
    for key, name in (("a", "A2"), ("e", "E")):
        rows = read_jsonl(OUT / f"rc{key}_v70.collect.jsonl")
        served += [{"set": name, "uid": r["uid"], "gold": r["gold"], "shown": r["final"].get("shown"), "decider": r["final"].get("decider"),
                    "degraded": bool(r["final"].get("degraded"))} for r in rows]
    projected = {r["uid"]: r for r in fm.project(["A2", "E"], 0.70)}
    pooled = fm.summarise(served)
    base = fm.summarise(fm.project(["A2", "E"], 2.0))
    need = int(-(-base["correct"] * 1.3 // 1))
    differ = [r for r in served if (projected[r["uid"]]["shown"] is not None) != (r["shown"] is not None) or projected[r["uid"]]["shown"] != r["shown"]]
    lo = pooled["precision_wilson_lower"]
    ok = (pooled["precision"] is not None and pooled["precision"] >= 0.85 and lo >= 0.80 and pooled["false_supported_wilson95"][1] <= 0.08
          and pooled["correct"] >= need)
    metrics = {"served_pooled": pooled, "projected_pooled": fm.summarise(list(projected.values())), "correct_needed": need,
               "claims_run": len(served), "claims_degraded": sum(r["degraded"] for r in served),
               "claims_where_served_differs_from_projection": len(differ),
               "A2_served": fm.summarise([r for r in served if r["set"] == "A2"]), "E_served": fm.summarise([r for r in served if r["set"] == "E"]),
               "wilson_precision_interval": list(wilson_interval(pooled["correct"], pooled["decidable_shown"])) if pooled["decidable_shown"] else None,
               "served_bars_met": bool(ok)}
    print(json.dumps(metrics, indent=1))
    h = fm.write_result("factcheck_match_served_confirmation", metrics)
    print(f"served bars met: {ok}; written results/{h}.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--set", choices=("a", "b", "d", "e"), required=True)
    c.add_argument("--suffix", default="", help="write rc<set><suffix>.collect.jsonl (the Stage 4 confirmation run uses _v70)")
    c.add_argument("--only", default=None, help="only the claims of this part (A2)")
    sub.add_parser("confirm")
    sub.add_parser("report")
    g = sub.add_parser("diagnose")
    g.add_argument("--set", choices=("b", "a1", "e", "f", "g"), required=True)
    g.add_argument("--suffix", default="", help="write diag_<set><suffix>.jsonl (the guard test uses _A and _B)")
    sub.add_parser("tally")
    args = ap.parse_args()
    if args.cmd == "diagnose":
        return diagnose(args.set, args.suffix)
    if args.cmd == "confirm":
        return confirm()
    return collect(args.set, args.suffix, args.only) if args.cmd == "collect" else tally() if args.cmd == "tally" else report()


if __name__ == "__main__":
    raise SystemExit(main())
