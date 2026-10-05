"""The development step of docs/translation-route-protocol.md: which translation route gives the best English for a romanized claim?

    python scripts/translation_route_check.py        # needs the GPU free: stop the server first

For each romanized rendering in RC-D the claim span is extracted exactly as the served pipeline does (preprocess, claim gate, extractor), then three English candidates are made:
V0 (served): lexicon transliteration then NLLB; V1: the Latin text passed to NLLB as typed; V2: whichever of V0 and V1 is closer (BGE-M3) to the original sentence.
The reference is the English rendering of the SAME claim (its extracted claim span). Measures: BGE-M3 cosine to the reference (primary), chrF, negation preservation.
No verdict is involved. Writes results/<hash>.json through the project's common utilities. The selection rule is in the protocol and is applied by this script.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

SEED = 42
NEG = re.compile(r"\b(not|no|never|cannot|without|none|neither|nor)\b|n't|n 't|\bcan 't\b", re.I)
RCD_EXCLUDED = {8, 9, 14, 15, 68, 83}


def chrf(hyp: str, ref: str, n_max: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score (chrF, beta 2), averaged over n = 1..6, on the sentence with spaces removed."""
    h, r = re.sub(r"\s+", "", hyp), re.sub(r"\s+", "", ref)
    ps, rs = [], []
    for n in range(1, n_max + 1):
        hc = Counter(h[i:i + n] for i in range(len(h) - n + 1))
        rc = Counter(r[i:i + n] for i in range(len(r) - n + 1))
        if not hc or not rc:
            continue
        match = sum((hc & rc).values())
        ps.append(match / sum(hc.values()))
        rs.append(match / sum(rc.values()))
    if not ps:
        return 0.0
    p, r_ = sum(ps) / len(ps), sum(rs) / len(rs)
    return 0.0 if p + r_ == 0 else (1 + beta**2) * p * r_ / (beta**2 * p + r_)


def claim_span(orch, text: str) -> tuple[str, str, list[str]]:
    """(claim text, language, forms) as the served pipeline would hand them to the translator."""
    from pipeline.contracts import Claim, Trace

    trace = Trace(request_id="rc-d")
    orch.preprocess.run(trace, text)
    if trace.pre.lang == "other":
        return trace.pre.normalized.strip(), "other", [text]
    ok = orch.claims.check_worthy(trace)
    if ok:
        orch.claims.extract(trace)
        claim = trace.claims[0]
    else:
        claim = Claim(claim_id="c1", text=trace.pre.normalized.strip(), span=None)
    return claim.text, trace.pre.lang, orch._claim_forms(trace, claim, None)


def main() -> int:
    import numpy as np

    from common.hashing import canonical_json, sha256_bytes, sha256_file
    from common.io_jsonl import write_json
    from common.provenance import env_info, git_info
    from common.seeds import set_all_seeds
    from pipeline.live import default_encode
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    seeded = set_all_seeds(SEED)
    orch = Orchestrator(PipelineConfig.load("configs/pipeline/dev.yaml"))
    translator = orch._get_translator()
    rows = [r for r in csv.DictReader((ROOT / "data" / "private" / "real_forwards_triplets.csv").open(encoding="utf-8-sig", newline=""))
            if int(r["id"]) not in RCD_EXCLUDED]
    clusters: dict[int, dict[str, str]] = {}
    for r in rows:
        clusters.setdefault((int(r["id"]) - 1) // 3, {})[r["language"]] = r["text"]
    items = []
    for cid, group in sorted(clusters.items()):
        if "English" not in group:
            continue
        ref, _, _ = claim_span(orch, group["English"])
        for lang_label in ("Hindi — Roman", "Punjabi — Roman"):
            if lang_label in group:
                text, lang, forms = claim_span(orch, group[lang_label])
                if lang not in ("hi", "pa"):
                    continue
                native = forms[-1] if len(forms) > 1 else text
                v0 = translator.to_english(native, lang)
                v1 = translator.translate(text, lang, "en")
                items.append({"cluster": cid, "lang": lang, "original": text, "reference": ref, "V0": v0, "V1": v1, "translit_changed_text": native != text})
    enc = default_encode
    for it in items:
        vecs = np.array(enc([it["original"], it["reference"], it["V0"], it["V1"]]), dtype=float)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        it["cos_to_original"] = {"V0": float(vecs[0] @ vecs[2]), "V1": float(vecs[0] @ vecs[3])}
        it["V2"] = it["V0"] if it["cos_to_original"]["V0"] >= it["cos_to_original"]["V1"] else it["V1"]
        it["V2_chose"] = "V0" if it["V2"] == it["V0"] else "V1"
        for v, vec in (("V0", vecs[2]), ("V1", vecs[3]), ("V2", vecs[2] if it["V2"] == it["V0"] else vecs[3])):
            it[f"cos_{v}"] = float(vecs[1] @ vec)
            it[f"chrf_{v}"] = chrf(it[v], it["reference"])
            it[f"neg_{v}"] = bool(NEG.search(it[v]))
        it["ref_neg"] = bool(NEG.search(it["reference"]))
    out_path = ROOT / "reports" / "real_claims" / "translation_route_items.json"
    out_path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    def stats(v: str, sel: list[dict]) -> dict:
        negs = [i for i in sel if i["ref_neg"]]
        return {"n": len(sel), "cosine_to_reference": float(np.mean([i[f"cos_{v}"] for i in sel])), "chrf": float(np.mean([i[f"chrf_{v}"] for i in sel])),
                "negation_preserved": (sum(i[f"neg_{v}"] for i in negs) / len(negs)) if negs else None, "references_with_negation": len(negs)}

    metrics: dict = {"clusters": len({i["cluster"] for i in items}), "items": len(items)}
    for name, sel in (("all", items), ("hindi", [i for i in items if i["lang"] == "hi"]), ("punjabi", [i for i in items if i["lang"] == "pa"])):
        metrics[name] = {v: stats(v, sel) for v in ("V0", "V1", "V2")}
    metrics["V2_chose_V1_share"] = sum(i["V2_chose"] == "V1" for i in items) / max(len(items), 1)

    ids = sorted({i["cluster"] for i in items})
    by_cluster = {c: [i for i in items if i["cluster"] == c] for c in ids}
    idx = np.random.default_rng(SEED).integers(0, len(ids), size=(1000, len(ids)))
    verdicts = {}
    for v in ("V1", "V2"):
        d = np.array([np.mean([i[f"cos_{v}"] - i["cos_V0"] for i in by_cluster[c]]) for c in ids])
        boots = d[idx].mean(axis=1)
        diff = metrics["all"][v]["cosine_to_reference"] - metrics["all"]["V0"]["cosine_to_reference"]
        lo = float(np.percentile(boots, 2.5))
        neg_ok = (metrics["all"][v]["negation_preserved"] or 0) >= (metrics["all"]["V0"]["negation_preserved"] or 0) - 0.02
        verdicts[v] = {"cosine_difference_vs_V0": diff, "bootstrap95": [lo, float(np.percentile(boots, 97.5))],
                       "qualifies": bool(diff >= 0.03 and lo > 0 and neg_ok), "negation_preservation_ok": bool(neg_ok)}
    metrics["selection"] = verdicts
    qual = [v for v in ("V1", "V2") if verdicts[v]["qualifies"]]
    metrics["selected_variant"] = max(qual, key=lambda v: verdicts[v]["cosine_difference_vs_V0"]) if qual else None
    print(json.dumps(metrics, indent=1))
    cfg = {"experiment": "p9_translation_route_dev", "task": "translation_route", "protocol": "docs/translation-route-protocol.md", "seed": SEED}
    sha = sha256_file(ROOT / "docs" / "translation-route-protocol.md")
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + canonical_json(metrics))[:12]
    write_json(ROOT / "results" / f"{h}.json", {
        "config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"], "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_info(), "env": env_info(), "seed": SEED, "seeded_libraries": seeded, "inputs": {"config": cfg, "protocol_sha256": sha}, "metrics": metrics})
    print(f"selected variant: {metrics['selected_variant']}; written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
