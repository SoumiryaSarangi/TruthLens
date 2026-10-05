"""The polarity guard test of docs/polarity-guard-protocol.md, computed offline (CPU only; the owner's server is not disturbed).

    CUDA_VISIBLE_DEVICES="" python scripts/polarity_guard_check.py

The guard blocks a live fact-check match when DeBERTa (premise = the matched fact-checked claim text, hypothesis = the English claim) gives
P(Contradiction) of at least 0.5. It can only remove verdicts. RC-F (paraphrases and negations written by the owner) is the test; A1, B, A2 and
RC-E give the retention check from their stored projections at tau 0.70. A blocked match is counted as silent (the served fall-through to
Wikipedia is what the served confirmation run measures). Run once on the real data: the rule was fixed in the protocol before this existed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "reports" / "real_claims"
TAU = 0.70
GUARD_P = 0.5
SEED = 42


def wrong(gold: str, shown: str | None) -> bool:
    return shown in ("Supported", "Refuted") and (shown == "Supported") != (gold == "T")


def served_shown(d: dict) -> str | None:
    ok = d.get("verdict") in ("Supported", "Refuted") and not d.get("abstained") and (bool(d.get("live_sources")) or d.get("path") == "fast")
    return d["verdict"] if ok else None


def nli_model():
    from pipeline.orchestrator import LIVE_NLI_MODEL
    from stance.nli import NLIStance

    return NLIStance(model_id=LIVE_NLI_MODEL, max_length=256, device="cpu", offload=False)


def match_rows_rcf() -> list[dict]:
    """RC-F rows with the served outcome and the recomputed best match (with its claim text)."""
    import factcheck_match_curve as fm
    import real_claims as rc
    from pipeline.live import default_encode
    from retrieval.live.factcheck import GoogleFactCheck

    diag = {r["uid"]: r["diag"] for r in rc.read_jsonl(OUT / "diag_f.jsonl")}
    path = OUT / "pg_match_F.jsonl"
    done = {r["uid"]: r for r in rc.read_jsonl(path)}
    fc = GoogleFactCheck()
    rows = []
    for c in rc.rcf_claims():
        d = diag[c["uid"]]
        if c["uid"] not in done:
            forms = [c["text"]] + ([d["claim_en"]] if d.get("claim_en") and d["claim_en"] != c["text"] else [])
            m = fm.best_match(fc, default_encode, forms)
            done[c["uid"]] = {"uid": c["uid"], "match": m, "english": d.get("claim_en") or c["text"]}
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(done[c["uid"]], ensure_ascii=False) + "\n")
        decider_fc = d.get("path") == "fast" or bool(d.get("match"))
        rows.append({**c, "shown": served_shown(d), "decider": "factcheck" if decider_fc else "other",
                     "match": done[c["uid"]]["match"], "english": done[c["uid"]]["english"]})
    return rows


def natural_rows() -> list[dict]:
    """The fact-check-decided shown verdicts of A1, B, A2 and RC-E at tau 0.70 (the projection), with the recomputed match."""
    import factcheck_match_curve as fm
    import real_claims as rc
    from pipeline.live import default_encode
    from retrieval.live.factcheck import GoogleFactCheck

    fc = GoogleFactCheck()
    out = []
    for name in ("A1", "B", "A2", "E"):
        claims = {c["uid"]: c for c in fm.claims_for(name)}
        path = OUT / f"pg_match_{name}.jsonl"
        done = {r["uid"]: r for r in rc.read_jsonl(path)}
        for r in fm.project([name], TAU):
            if not (r["shown"] and r["decider"] == "factcheck"):
                continue
            if r["uid"] not in done:
                done[r["uid"]] = {"uid": r["uid"], "match": fm.best_match(fc, default_encode, claims[r["uid"]]["forms"]),
                                  "english": claims[r["uid"]]["forms"][-1]}
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(done[r["uid"]], ensure_ascii=False) + "\n")
            out.append({"set": name, "uid": r["uid"], "gold": r["gold"], "shown": r["shown"], "match": done[r["uid"]]["match"],
                        "english": done[r["uid"]]["english"]})
    return out


def apply_guard(nli, rows: list[dict]) -> None:
    """Adds p_contra and blocked to every row whose shown verdict was decided by a fact-check match with an English matched claim."""
    todo = [r for r in rows if r.get("shown") and r.get("decider", "factcheck") == "factcheck" and r["match"] and r["match"].get("lang") == "en"
            and r["match"].get("claim_text")]
    results = nli.score_pairs([(r["match"]["claim_text"], r["english"]) for r in todo])
    for r, res in zip(todo, results, strict=True):
        r["p_contra"] = res.probs.get("Refutes", 0.0)
        r["blocked"] = r["p_contra"] >= GUARD_P
    for r in rows:
        r.setdefault("blocked", False)


def after(r: dict) -> str | None:
    return None if r["blocked"] else r["shown"]


def counts(rows: list[dict]) -> dict:
    sh0 = [r for r in rows if r["shown"]]
    sh1 = [r for r in rows if after(r)]
    return {"n": len(rows), "shown_without": len(sh0), "shown_with": len(sh1),
            "correct_without": sum(not wrong(r["gold"], r["shown"]) for r in sh0), "correct_with": sum(not wrong(r["gold"], after(r)) for r in sh1),
            "wrong_without": sum(wrong(r["gold"], r["shown"]) for r in sh0), "wrong_with": sum(wrong(r["gold"], after(r)) for r in sh1),
            "false_supported_without": sum(r["shown"] == "Supported" and r["gold"] == "F" for r in rows),
            "false_supported_with": sum(after(r) == "Supported" and r["gold"] == "F" for r in rows),
            "blocked": sum(r["blocked"] for r in rows)}


def main() -> int:
    from datetime import UTC, datetime

    import numpy as np

    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds

    seeded = set_all_seeds(SEED)
    nli = nli_model()
    rcf = match_rows_rcf()
    apply_guard(nli, rcf)
    nat = natural_rows()
    for r in nat:
        r["decider"] = "factcheck"
    apply_guard(nli, nat)

    metrics: dict = {"tau_live_match": TAU, "guard_threshold_p_contradiction": GUARD_P}
    for kind in ("paraphrase", "negation"):
        sub = [r for r in rcf if r["kind"] == kind]
        metrics[f"RCF_{kind}"] = counts(sub)
    metrics["RCF_paraphrase_non_verbatim"] = counts([r for r in rcf if r["kind"] == "paraphrase" and not r["verbatim"]])
    metrics["natural_sets_factcheck_decided"] = counts(nat)
    metrics["natural_by_set"] = {s: counts([r for r in nat if r["set"] == s]) for s in ("A1", "B", "A2", "E")}
    metrics["rcf_factcheck_decided_without_an_english_match_to_check"] = sum(
        1 for r in rcf if r["shown"] and r["decider"] == "factcheck" and not r.get("p_contra") and r.get("p_contra") != 0.0)

    neg = metrics["RCF_negation"]
    para = metrics["RCF_paraphrase"]
    nat_c = metrics["natural_sets_factcheck_decided"]
    # cluster bootstrap over sources for the share of wrong negations that remain with the guard
    sources = sorted({r["source_id"] for r in rcf})
    w0 = np.array([sum(wrong(r["gold"], r["shown"]) for r in rcf if r["kind"] == "negation" and r["source_id"] == s) for s in sources], float)
    w1 = np.array([sum(wrong(r["gold"], after(r)) for r in rcf if r["kind"] == "negation" and r["source_id"] == s) for s in sources], float)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(sources), size=(1000, len(sources)))
    den = w0[idx].sum(axis=1)
    ratio = (w1[idx].sum(axis=1)[den > 0] / den[den > 0])
    metrics["negation_wrong_remaining_share_cluster_bootstrap95"] = [float(np.percentile(ratio, 2.5)), float(np.percentile(ratio, 97.5))] if len(ratio) else None

    informative = neg["wrong_without"] >= 6
    rule1 = informative and neg["wrong_with"] <= 0.25 * neg["wrong_without"]
    rule2a = para["correct_without"] > 0 and para["correct_with"] >= 0.85 * para["correct_without"]
    rule2b = nat_c["correct_without"] > 0 and nat_c["correct_with"] >= 0.90 * nat_c["correct_without"]
    all_rows = rcf + nat
    rule3 = all(not (wrong(r["gold"], after(r)) and not wrong(r["gold"], r["shown"])) for r in all_rows)
    rule4 = (neg["false_supported_with"] + para["false_supported_with"]) == 0
    metrics["rules"] = {"informative_at_least_6_wrong_negations_without_guard": informative, "1_removes_wrong_negations": bool(rule1),
                        "2a_keeps_right_paraphrases_85": bool(rule2a), "2b_keeps_right_natural_90": bool(rule2b), "3_no_new_wrong": bool(rule3),
                        "4_zero_false_supported_with_guard": bool(rule4)}
    metrics["guard_adopted_by_the_rule"] = bool(rule1 and rule2a and rule2b and rule3 and rule4)
    print(json.dumps(metrics, indent=1))
    print()
    for r in rcf:
        if r["blocked"] or wrong(r["gold"], r["shown"]):
            print(f"  [{r['kind']} gold={r['gold']} shown={r['shown']} blocked={r['blocked']} p_contra={r.get('p_contra')}] {r['text'][:80]}")
    cfg = {"experiment": "p9_polarity_guard", "task": "polarity_guard", "protocol": "docs/polarity-guard-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "polarity-guard-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + canonical_json(metrics))[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha},
        "metrics": metrics})
    print(f"written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
