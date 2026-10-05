"""Stage 1 development check of docs/live-retrieval-v2-protocol.md (correction 2): does v2 find more pages that are about the claim?

    CUDA_VISIBLE_DEVICES="" python scripts/retrieval_v2_check.py

For every gold-T/F claim of B and of A1, v1 and v2 queries go to the live Wikipedia API; the candidates are scored by BGE-M3 (on CPU, so the
owner's server is not disturbed) and a claim counts when at least one page passes the UNCHANGED relevance floor and the UNCHANGED title gate.
No fact-check calls, no NLI, no verdict. Resumable: the per-claim rows are appended to reports/real_claims/retrieval_v2_check.jsonl.
Writes results/<hash>.json through the project's common utilities.
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


class NoFactCheck:
    available = False


def claims() -> list[dict]:
    import real_claims as rc

    diag = {r["uid"]: r["diag"].get("claim_en") for r in rc.read_jsonl(OUT / "diag_b.jsonl")}
    out = []
    for c in rc.rcb_claims():
        if c["gold"] in ("T", "F"):
            forms = [c["text"]] + ([diag[c["uid"]]] if diag.get(c["uid"]) and diag[c["uid"]] != c["text"] else [])
            out.append({**c, "forms": forms})
    for c in rc.rca_claims():
        if c["part"] == "A1" and c["gold"] in ("T", "F"):
            out.append({**c, "forms": [c["text"]]})
    return out


def grounded_pages(live, forms: list[str]) -> tuple[list[str], int]:
    from pipeline.live import LIVE_RELEVANCE_FLOOR, title_grounded

    calls = []
    original = live.wikipedia._search

    def counting(lang, query, limit=None):
        calls.append(query)
        return original(lang, query, limit)

    live.wikipedia._search = counting
    try:
        found = live.gather(forms, "en")
    finally:
        live.wikipedia._search = original
    pages = [p.title for p in found.passages
             if p.source == "wikipedia" and p.lang == "en" and p.cosine >= LIVE_RELEVANCE_FLOOR and title_grounded(p.title, forms)]
    return pages, len(calls)


def main() -> int:
    import real_claims as rc
    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds
    from eval.metrics import wilson_interval
    from pipeline.live import LiveEvidence

    seeded = set_all_seeds(SEED)
    path = OUT / "retrieval_v2_check.jsonl"
    done = {r["uid"] for r in rc.read_jsonl(path)}
    todo = [c for c in claims() if c["uid"] not in done]
    print(f"{len(todo)} claims to do, {len(done)} done", flush=True)
    lives = {v: LiveEvidence(factcheck=NoFactCheck(), to_english=True, retrieval_v2=v) for v in (False, True)}
    for i, c in enumerate(todo, 1):
        row = {"uid": c["uid"], "part": c["part"], "gold": c["gold"]}
        for v, live in lives.items():
            try:
                pages, n = grounded_pages(live, c["forms"])
                row["v2" if v else "v1"] = {"pages": pages, "requests": n}
            except Exception as exc:  # network trouble: recorded, the claim is kept out of the shares
                row["v2" if v else "v1"] = {"error": f"{type(exc).__name__}: {exc}"[:150]}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if i % 10 == 0:
            print(f"  {i}/{len(todo)}", flush=True)

    rows = [r for r in rc.read_jsonl(path) if "pages" in r.get("v1", {}) and "pages" in r.get("v2", {})]
    errors = len(rc.read_jsonl(path)) - len(rows)
    metrics: dict = {"claims_with_both": len(rows), "claims_with_a_fetch_error": errors}
    for name, subset in (("pooled", rows), ("B", [r for r in rows if r["part"] == "B"]), ("A1", [r for r in rows if r["part"] == "A1"])):
        n = len(subset)
        s1 = sum(bool(r["v1"]["pages"]) for r in subset)
        s2 = sum(bool(r["v2"]["pages"]) for r in subset)
        metrics[name] = {"n": n, "v1_with_grounded_page": s1, "v2_with_grounded_page": s2,
                         "v1_share": s1 / n if n else None, "v2_share": s2 / n if n else None,
                         "v1_wilson95": list(wilson_interval(s1, n)) if n else None, "v2_wilson95": list(wilson_interval(s2, n)) if n else None,
                         "ratio": (s2 / s1) if s1 else None,
                         "requests_per_claim_v1_mean": sum(r["v1"]["requests"] for r in subset) / n if n else None,
                         "requests_per_claim_v2_mean": sum(r["v2"]["requests"] for r in subset) / n if n else None,
                         "requests_per_claim_v2_max": max((r["v2"]["requests"] for r in subset), default=None)}
    p = metrics["pooled"]
    ok = (p["ratio"] is not None and p["ratio"] >= 1.25 and all(
        metrics[k]["v2_share"] >= metrics[k]["v1_share"] for k in ("B", "A1") if metrics[k]["n"]))
    metrics["stage1_retrieval_check_passes"] = bool(ok)
    print(json.dumps(metrics, indent=1))
    cfg = {"experiment": "p9_retrieval_v2_check", "task": "retrieval_v2_check", "protocol": "docs/live-retrieval-v2-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "live-retrieval-v2-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + canonical_json(metrics))[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": metrics})
    print(f"written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
