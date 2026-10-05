"""Stage 4 of docs/live-retrieval-v2-protocol.md: the live fact-check match threshold as a precision-coverage curve.

    CUDA_VISIBLE_DEVICES="" python scripts/factcheck_match_curve.py dev      # A1 + B: the curve, and the mechanical choice of tau
    CUDA_VISIBLE_DEVICES="" python scripts/factcheck_match_curve.py final    # A2 + RC-E, ONCE, at the tau the dev step chose

Nothing here touches the served system. For every claim the same Google Fact Check queries as the live path are made (cached), each hit is
scored by BGE-M3 on CPU against the fact-checked claim text as `LiveEvidence.gather` does, and the best hit with a rating that maps to Supported
or Refuted is stored in reports/real_claims/fc_match_<set>.jsonl. Offline, a claim is shown at tau when its best cosine is at least tau, else it keeps
what the collected v1 run showed. The key is read from .env by the project's own loader and is never printed.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "reports" / "real_claims"
SEED = 42
TAUS = (0.90, 0.85, 0.80, 0.75, 0.70)
V1_SHOWN_FILES = {"A1": "rca", "A2": "rca", "B": "rcb", "E": "rce"}


def claims_for(name: str) -> list[dict]:
    import real_claims as rc

    diag_file = {"B": "diag_b.jsonl", "E": "diag_e.jsonl"}.get(name)
    english = {r["uid"]: r["diag"].get("claim_en") for r in rc.read_jsonl(OUT / diag_file)} if diag_file else {}
    if name in ("A1", "A2"):
        return [{**c, "forms": [c["text"]]} for c in rc.rca_claims() if c["part"] == name]
    base = rc.rcb_claims() if name == "B" else rc.rcb_claims("real_forwards_new.csv", "rce", "E")
    return [{**c, "forms": [c["text"]] + ([english[c["uid"]]] if english.get(c["uid"]) and english[c["uid"]] != c["text"] else [])} for c in base]


def best_match(fc, encode, forms: list[str]) -> dict | None:
    from data.verdicts import rating_to_verdict
    from pipeline.live import GOOGLE_QUERY_CHARS, _cosines

    hits = {}
    for form in forms:
        for hit in fc.search(form[:GOOGLE_QUERY_CHARS]):
            hits.setdefault(hit.url, hit)
    hits = list(hits.values())
    cos = _cosines(encode, forms, [h.claim_text or h.title for h in hits])
    best = None
    for hit, c in zip(hits, cos, strict=True):
        verdict = rating_to_verdict([hit.rating]) if hit.rating else None
        if verdict in ("Supported", "Refuted") and (best is None or c > best["cosine"]):
            best = {"cosine": float(c), "verdict": verdict, "publisher": hit.publisher or "", "url": hit.url}
    return best


def collect_matches(name: str) -> list[dict]:
    import real_claims as rc
    from pipeline.live import default_encode
    from retrieval.live.factcheck import GoogleFactCheck

    path = OUT / f"fc_match_{name}.jsonl"
    done = {r["uid"] for r in rc.read_jsonl(path)}
    fc = GoogleFactCheck()
    if not fc.available:
        raise SystemExit("no Google Fact Check key configured (.env)")
    todo = [c for c in claims_for(name) if c["uid"] not in done]
    print(f"{name}: {len(todo)} claims to score, {len(done)} done", flush=True)
    for i, c in enumerate(todo, 1):
        try:
            match = best_match(fc, default_encode, c["forms"])
            row = {"uid": c["uid"], "gold": c["gold"], "match": match, "family": c.get("family")}
        except Exception as exc:  # a fetch problem: recorded, the claim keeps its v1 result
            row = {"uid": c["uid"], "gold": c["gold"], "match": None, "error": f"{type(exc).__name__}"[:60], "family": c.get("family")}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
    return rc.read_jsonl(path)


def project(sets: list[str], tau: float) -> list[dict]:
    """Per-claim shown verdict at tau: the fact-check match decides first (as in the orchestrator), else what v1 showed."""
    import real_claims as rc

    rows = []
    for name in sets:
        v1 = {r["uid"]: r for r in rc.read_jsonl(OUT / f"{V1_SHOWN_FILES[name]}.collect.jsonl")}
        for m in rc.read_jsonl(OUT / f"fc_match_{name}.jsonl"):
            first = v1[m["uid"]]["final"]
            if m["match"] and m["match"]["cosine"] >= tau:
                shown, decider, pub = m["match"]["verdict"], "factcheck", m["match"]["publisher"]
            else:
                shown, decider, pub = first.get("shown"), first.get("decider"), ""
            rows.append({"set": name, "uid": m["uid"], "gold": m["gold"], "shown": shown, "decider": decider, "publisher": pub,
                         "family": m.get("family") or m["uid"]})
    return rows


def summarise(rows: list[dict]) -> dict:
    from eval.metrics import real_claims_metrics, wilson_interval

    m = real_claims_metrics([{"gold": r["gold"], "shown": r["shown"], "decider": r["decider"]} for r in rows])["all"]
    lo = wilson_interval(m["correct"], m["decidable_shown"])[0] if m["decidable_shown"] else None
    return {"n": m["n"], "shown": m["shown"], "decidable_shown": m["decidable_shown"], "correct": m["correct"], "precision": m["precision"],
            "precision_wilson_lower": lo, "false_supported": m["false_supported"], "gold_false": m["gold_false"],
            "false_supported_wilson95": m["false_supported_wilson95"], "shown_on_unverifiable": m["shown_on_unverifiable"],
            "coverage": m["coverage"]}


def write_result(task: str, metrics: dict) -> str:
    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds

    seeded = set_all_seeds(SEED)
    cfg = {"experiment": f"p9_{task}", "task": task, "protocol": "docs/live-retrieval-v2-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "live-retrieval-v2-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + canonical_json(metrics))[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": task, "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": metrics})
    return h


def dev() -> int:
    for name in ("A1", "B"):
        collect_matches(name)
    v1_rows = project(["A1", "B"], 2.0)          # tau above any cosine: nothing is a match, so exactly the collected v1 result
    base = summarise(v1_rows)
    need = int(-(-base["correct"] * 1.3 // 1))   # 30% more correct shown decidable verdicts, rounded up
    table, chosen = {}, None
    for tau in TAUS:                              # highest first; the LOWEST passing tau wins
        s = summarise(project(["A1", "B"], tau))
        pubs: dict[str, int] = {}
        for r in project(["A1", "B"], tau):
            if r["shown"] and r["decider"] == "factcheck":
                pubs[r["publisher"]] = pubs.get(r["publisher"], 0) + 1
        s["fc_shown_by_publisher"] = dict(sorted(pubs.items(), key=lambda kv: -kv[1])[:8])
        s["meets_rule"] = bool(s["precision"] is not None and s["precision"] >= 0.90 and s["false_supported"] == 0 and s["correct"] >= need)
        table[f"{tau:.2f}"] = s
        if s["meets_rule"]:
            chosen = tau
    metrics = {"v1_baseline_A1_B": base, "correct_needed_for_gain": need, "by_tau": table, "chosen_tau": chosen}
    print(json.dumps(metrics, indent=1))
    h = write_result("factcheck_match_curve_dev", metrics)
    (OUT / "stage4_choice.json").write_text(json.dumps({"chosen_tau": chosen, "dev_result": h}), encoding="utf-8")
    print(f"chosen tau: {chosen}; written results/{h}.json")
    return 0


def final() -> int:
    choice = json.loads((OUT / "stage4_choice.json").read_text(encoding="utf-8"))
    tau = choice["chosen_tau"]
    if tau is None:
        raise SystemExit("the dev step chose no tau: Stage 4 is dropped, there is nothing to test")
    lock = OUT / "stage4_final.lock"
    if lock.exists():
        raise SystemExit("the final test has been run once already (stage4_final.lock): it is not repeated")
    for name in ("A2", "E"):
        collect_matches(name)
    from eval.metrics import cluster_rates_ci

    rows = project(["A2", "E"], tau)
    base = summarise(project(["A2", "E"], 2.0))
    pooled = summarise(rows)
    need = int(-(-base["correct"] * 1.3 // 1))
    fams = {f: i for i, f in enumerate(sorted({r["family"] for r in rows if r["set"] == "E"}))}
    erows = [{"cluster": fams[r["family"]], "gold": r["gold"], "shown": r["shown"]} for r in rows if r["set"] == "E"]
    metrics = {"tau": tau, "pooled_v1_baseline": base, "pooled_at_tau": pooled, "correct_needed_for_gain": need,
               "A2_at_tau": summarise([r for r in rows if r["set"] == "A2"]), "E_at_tau": summarise([r for r in rows if r["set"] == "E"]),
               "E_cluster_rates": cluster_rates_ci(erows)}
    ok = (pooled["precision"] is not None and pooled["precision"] >= 0.85 and pooled["precision_wilson_lower"] >= 0.80
          and pooled["false_supported_wilson95"][1] <= 0.08 and pooled["correct"] >= need)
    metrics["final_bars_met"] = bool(ok)
    print(json.dumps(metrics, indent=1))
    h = write_result("factcheck_match_curve_final", metrics)
    lock.write_text(h, encoding="utf-8")
    print(f"final bars met: {ok}; written results/{h}.json")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit(dev() if mode == "dev" else final() if mode == "final" else print(__doc__) or 2)
