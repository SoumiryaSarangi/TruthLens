"""The polarity guard v2 rule of docs/polarity-guard-v2-protocol.md, computed once from the two served runs.

    python scripts/polarity_guard_v2_check.py

Arm A: the served system without the guard (diag_g_A.jsonl for RC-G; rca_v70 and rce_v70 for A2 and RC-E, the recorded run f0d7ab316ff0).
Arm B: the same system with `live_match_guard: true` (diag_g_B.jsonl; rca_guard and rce_guard). Everything is read from the stored per-sentence results;
no model is run. Refuses to run if an arm is incomplete, and writes results/<hash>.json through the project's common utilities.
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


def is_wrong(gold: str, shown: str | None) -> bool:
    return shown in ("Supported", "Refuted") and (shown == "Supported") != (gold == "T")


def diag_shown(d: dict) -> str | None:
    ok = d.get("verdict") in ("Supported", "Refuted") and not d.get("abstained") and (bool(d.get("live_sources")) or d.get("path") == "fast")
    return d["verdict"] if ok else None


def load_rcg(arm: str) -> dict[str, dict]:
    import real_claims as rc

    rows = rc.read_jsonl(OUT / f"diag_g_{arm}.jsonl")
    out = {}
    for r in rows:
        d = r["diag"]
        notes = " | ".join(d.get("notes") or [])
        out[r["uid"]] = {"uid": r["uid"], "gold": r["gold"], "kind": r["kind"], "source_id": r["source_id"], "shown": diag_shown(d),
                         "fc_decided": d.get("path") == "fast" or bool(d.get("match")), "blocked": "BLOCKED" in notes,
                         "unchecked": "not checked" in notes, "degraded": any(n.startswith("degraded") for n in (d.get("notes") or []))}
    return out


def load_natural(arm: str) -> dict[str, dict]:
    import real_claims as rc

    out = {}
    for key, part, suffix in (("a", "A2", "_v70" if arm == "A" else "_guard"), ("e", None, "_v70" if arm == "A" else "_guard")):
        for r in rc.read_jsonl(OUT / f"rc{key}{suffix}.collect.jsonl"):
            if part and r["part"] != part:
                continue
            out[r["uid"]] = {"uid": r["uid"], "gold": r["gold"], "shown": r["final"].get("shown"), "degraded": bool(r["final"].get("degraded"))}
    return out


def tally(rows: dict[str, dict], kind: str | None = None) -> dict:
    sel = [r for r in rows.values() if kind is None or r.get("kind") == kind]
    shown = [r for r in sel if r["shown"]]
    return {"n": len(sel), "shown": len(shown), "correct": sum(not is_wrong(r["gold"], r["shown"]) for r in shown),
            "wrong": sum(is_wrong(r["gold"], r["shown"]) for r in shown),
            "false_supported": sum(r["shown"] == "Supported" and r["gold"] == "F" for r in sel)}


def main() -> int:
    import numpy as np

    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds

    seeded = set_all_seeds(SEED)
    a, b = load_rcg("A"), load_rcg("B")
    na, nb = load_natural("A"), load_natural("B")
    if len(a) != 78 or len(b) != 78 or len(na) != 335 or len(nb) != 335:
        raise SystemExit(f"an arm is incomplete (RC-G A {len(a)}/78, B {len(b)}/78; A2+RC-E A {len(na)}/335, B {len(nb)}/335): not computed")

    m: dict = {"rcg": {}, "natural": {}}
    for kind in ("paraphrase", "negation"):
        m["rcg"][kind] = {"A": tally(a, kind), "B": tally(b, kind)}
    m["rcg"]["B_blocked"] = sum(r["blocked"] for r in b.values())
    m["rcg"]["B_unchecked_fact_check_answers"] = sum(r["unchecked"] for r in b.values())
    m["rcg"]["degraded_A"] = sum(r["degraded"] for r in a.values())
    m["rcg"]["degraded_B"] = sum(r["degraded"] for r in b.values())
    m["natural"] = {"A": tally(na), "B": tally(nb), "degraded_A": sum(r["degraded"] for r in na.values()),
                    "degraded_B": sum(r["degraded"] for r in nb.values())}

    neg_a, neg_b = m["rcg"]["negation"]["A"], m["rcg"]["negation"]["B"]
    para_a, para_b = m["rcg"]["paraphrase"]["A"], m["rcg"]["paraphrase"]["B"]
    sources = sorted({r["source_id"] for r in a.values()})
    w0 = np.array([sum(is_wrong(r["gold"], r["shown"]) for r in a.values() if r["kind"] == "negation" and r["source_id"] == s) for s in sources], float)
    w1 = np.array([sum(is_wrong(r["gold"], b[r["uid"]]["shown"]) for r in a.values() if r["kind"] == "negation" and r["source_id"] == s) for s in sources], float)
    idx = np.random.default_rng(SEED).integers(0, len(sources), size=(1000, len(sources)))
    den = w0[idx].sum(axis=1)
    ratio = w1[idx].sum(axis=1)[den > 0] / den[den > 0]
    m["negation_wrong_remaining_share_cluster_bootstrap95"] = [float(np.percentile(ratio, 2.5)), float(np.percentile(ratio, 97.5))] if len(ratio) else None

    new_wrong = [uid for uid, r in {**b, **nb}.items()
                 if is_wrong(r["gold"], r["shown"]) and not is_wrong(({**a, **na})[uid]["gold"], ({**a, **na})[uid]["shown"])]
    m["new_wrong_in_B_not_in_A"] = new_wrong
    rules = {
        "1_informative_at_least_6_wrong_negations_in_A": neg_a["wrong"] >= 6,
        "2_wrong_negations_in_B_at_most_25pct_of_A": neg_a["wrong"] >= 6 and neg_b["wrong"] <= 0.25 * neg_a["wrong"],
        "3_right_paraphrases_kept_85pct": para_a["correct"] > 0 and para_b["correct"] >= 0.85 * para_a["correct"],
        "4_natural_right_kept_90pct_of_A": m["natural"]["A"]["correct"] > 0 and m["natural"]["B"]["correct"] >= 0.90 * m["natural"]["A"]["correct"],
        "5_no_new_wrong": not new_wrong,
        "6_no_false_supported_on_rcg_in_B": (neg_b["false_supported"] + para_b["false_supported"]) == 0,
    }
    m["rules"] = {k: bool(v) for k, v in rules.items()}
    m["guard_stays_on_by_the_rule"] = bool(all(rules.values()))
    print(json.dumps(m, indent=1))
    print("\nwrong negations still shown in B:")
    for r in b.values():
        if r["kind"] == "negation" and is_wrong(r["gold"], r["shown"]):
            print(f"  {r['uid']} gold={r['gold']} shown={r['shown']} unchecked={r['unchecked']}")
    cfg = {"experiment": "p9_polarity_guard_v2", "task": "polarity_guard_v2", "protocol": "docs/polarity-guard-v2-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "polarity-guard-v2-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + canonical_json(m))[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": m})
    print(f"written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
