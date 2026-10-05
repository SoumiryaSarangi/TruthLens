"""Measure the "Be careful" rule once (docs/careful-rule-protocol.md). CPU, rules only, no model.

    python scripts/careful_rule_check.py

True claims: AVeriTeC dev gold Supported (the gate) and FEVER fresh real-world-true (reported). False claims: AVeriTeC dev
gold Refuted. Baseline: the served dev prediction (the offline lean) for the same true claims. Also the 30 typical hoaxes.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import canonical_json, sha256_bytes, sha256_file  # noqa: E402
from common.io_jsonl import write_json  # noqa: E402
from common.provenance import env_info, git_info  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from eval.metrics import careful_rule_metrics, wilson_interval  # noqa: E402
from manipulation.hoax_cues import caution_cues  # noqa: E402

PROTOCOL = ROOT / "docs" / "careful-rule-protocol.md"


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def texts(dataset: str, label: str) -> list[tuple[str, str]]:
    gold = {r["uid"]: r["label"] for r in rows(ROOT / "data" / "splits" / dataset / "dev.jsonl")}
    return [(r["uid"], r["text"]) for r in rows(ROOT / "data" / "interim" / dataset / "dev.jsonl") if gold.get(r["uid"]) == label]


def main() -> int:
    seeded = set_all_seeds(SEED)
    served = {r["uid"]: r["pred"] for r in rows(ROOT / "results" / "preds" / "p6_verdict_served.jsonl")}
    true_av = texts("averitec", "Supported")
    false_av = texts("averitec", "Refuted")
    true_fever = texts("fever_fresh_truth", "Supported")
    hoaxes = json.loads((ROOT / "data" / "probe" / "hoax30.json").read_text(encoding="utf-8"))

    fired = lambda items: [bool(caution_cues(t)) for _, t in items]  # noqa: E731
    m = careful_rule_metrics(fired(true_av), fired(false_av), [served[u] == "Refuted" for u, _ in true_av],
                             [bool(caution_cues(h["text"])) for h in hoaxes])
    f_fever = fired(true_fever)
    m["fever_true_n"], m["fever_true_cautioned"] = len(f_fever), sum(f_fever)
    m["fever_true_rate"] = sum(f_fever) / len(f_fever)
    m["fever_true_wilson95"] = list(wilson_interval(sum(f_fever), len(f_fever)))
    cues = {}
    for _, t in false_av:
        for c in caution_cues(t):
            cues[c] = cues.get(c, 0) + 1
    m["false_cue_counts"] = dict(sorted(cues.items(), key=lambda kv: -kv[1]))
    print(json.dumps(m, indent=1))
    for gate, ok in m["gates"].items():
        print(f"  gate {gate}: {'PASS' if ok else 'FAIL'}")
    print("RULE R IS ADOPTED" if m["passes"] else "RULE R IS NOT ADOPTED (the lean-based wording stays)")

    cfg = {"experiment": "p9_careful_rule", "task": "careful_rule", "protocol": "docs/careful-rule-protocol.md", "seed": SEED}
    sha = sha256_file(PROTOCOL)
    h = sha256_bytes(canonical_json(cfg) + sha.encode() + sha256_file(ROOT / "src" / "manipulation" / "hoax_cues.py").encode())[:12]
    doc = {"config_hash": h, "experiment": cfg["experiment"], "task": cfg["task"],
           "created_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git": git_info(), "env": env_info(),
           "seed": SEED, "seeded_libraries": seeded,
           "inputs": {"config": cfg, "protocol_sha256": sha}, "metrics": m}
    write_json(ROOT / "results" / f"{h}.json", doc)
    print(f"written results/{h}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
