"""Faithfulness of the "which words mattered" view (docs/word-highlight-protocol.md, pre-registered).

    CUDA_VISIBLE_DEVICES="" python scripts/word_faithfulness.py [--set fresh_en] [--limit N]

For every claim of the stored `fever_fresh` run that got a Supported/Refuted verdict, find the 3 words
the occlusion view marks and compare the fall in the models' P(verdict) when those are deleted with
deleting 3 random words (20 draws, seed 42) and the 3 least influential words. The three gates are
computed by `eval.metrics.word_faithfulness_metrics`; this script only scores the deletions.

CPU only (the owner's server holds the GPU). Resumable: per-claim drops are cached in
reports/live_fever/<set>.words.jsonl, and the random draws are made for EVERY claim in file order so a
resumed run is identical to an uninterrupted one.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import canonical_json, sha256_bytes, sha256_file  # noqa: E402
from common.io_jsonl import write_json  # noqa: E402
from common.provenance import env_info, git_info  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from eval.metrics import word_faithfulness_metrics  # noqa: E402
from explain.occlusion import (  # noqa: E402
    TOP_K,
    bottom_indices,
    influences,
    split_words,
    top_indices,
    without,
)
from explain.words import STANCE_OF, class_probs  # noqa: E402

OUT = ROOT / "reports" / "live_fever"
PROTOCOL = ROOT / "docs" / "word-highlight-protocol.md"
N_RANDOM = 20
MIN_TOKENS = 6
LIVE_NLI = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
LIVE_PARTNER = "facebook/bart-large-mnli"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def population(rows: list[dict]) -> list[dict]:
    """Claims the shipped rule answered Supported/Refuted, with the passage the two models agreed on most."""
    out = []
    for rec in rows:
        shown = (rec.get("live") or {}).get("pred")
        if shown not in STANCE_OF or rec["n_results"] != 1 or len(rec["capture"]) != 1:
            continue
        cap = rec["capture"][0]
        stance = STANCE_OF[shown]
        best, best_p = None, -1.0
        for i, p in enumerate(cap["judged"]):
            if p["rating_stance"]:
                continue
            both = [rec["probs"][k][i][stance] for k in ("deberta", "bart") if rec["probs"][k][i]]
            if both and sum(both) / len(both) > best_p:
                best, best_p = i, sum(both) / len(both)
        if best is not None:
            out.append({"uid": rec["uid"], "verdict": shown, "hypothesis": cap["hypothesis"],
                        "premise": cap["judged"][best]["premise"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="fresh_en")
    ap.add_argument("--limit", type=int, default=0, help="smoke test only: score the first N claims, write no result")
    args = ap.parse_args()
    seeded = set_all_seeds(SEED)

    src = OUT / f"{args.set}.scored.jsonl"
    claims = population(read_jsonl(src))
    print(f"{args.set}: {len(claims)} claims with a shown verdict", flush=True)

    from stance.nli import NLIStance

    models = [NLIStance(model_id=LIVE_NLI, max_length=256, batch_size=8),
              NLIStance(model_id=LIVE_PARTNER, max_length=256, batch_size=8)]

    cache_path = OUT / f"{args.set}.words.jsonl"
    cache = {r["uid"]: r for r in read_jsonl(cache_path)} if cache_path.exists() and not args.limit else {}
    rng = np.random.default_rng(SEED)
    rows, skipped = [], 0
    t0 = time.time()
    for n, c in enumerate(claims):
        words = split_words(c["hypothesis"])
        # the random draws are consumed for every claim, so a resumed run matches an uninterrupted one
        draws = ([sorted(rng.choice(len(words), size=TOP_K, replace=False).tolist()) for _ in range(N_RANDOM)]
                 if len(words) >= MIN_TOKENS else [])
        if len(words) < MIN_TOKENS:
            skipped += 1
            continue
        if args.limit and len(rows) >= args.limit:
            break
        if c["uid"] in cache:
            rows.append(cache[c["uid"]])
            continue
        prem, hyp = c["premise"], c["hypothesis"]
        singles = [without(words, [i]) for i in range(len(words))]
        # the full pair and every single-word deletion, to choose the top and bottom words
        p = class_probs(models, [(prem, hyp)] + [(prem, s) for s in singles], c["verdict"])
        infl = influences(p[0], p[1:])
        top, bottom = top_indices(infl), bottom_indices(infl)
        if len(top) < TOP_K:                      # fewer than 3 words pushed toward the verdict: nothing to compare
            row = {"uid": c["uid"], "verdict": c["verdict"], "n_words": len(words), "no_top": True}
        else:
            sets = [top, bottom, *draws]
            q = class_probs(models, [(prem, without(words, s)) for s in sets], c["verdict"])
            drops = [p[0] - x for x in q]
            row = {"uid": c["uid"], "verdict": c["verdict"], "n_words": len(words),
                   "top_words": [words[i] for i in top], "drop_top": drops[0], "drop_bottom": drops[1],
                   "drop_random": float(np.mean(drops[2:]))}
        rows.append(row)
        if not args.limit:
            with cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  {n + 1}/{len(claims)}  {time.time() - t0:.0f}s  {row.get('top_words')}", flush=True)

    scored = [r for r in rows if not r.get("no_top")]
    no_top = len(rows) - len(scored)
    metrics = word_faithfulness_metrics([r["drop_top"] for r in scored], [r["drop_random"] for r in scored],
                                        [r["drop_bottom"] for r in scored])
    print(json.dumps({"claims_in_population": len(claims), "fewer_than_6_words": skipped,
                      "fewer_than_3_helpful_words": no_top, **metrics}, indent=1))
    for gate, ok in metrics["gates"].items():
        print(f"  gate {gate}: {'PASS' if ok else 'FAIL'}")
    print("THE WORD VIEW " + ("SHIPS" if metrics["passes"] else "STAYS OFF"))
    if args.limit:
        return 0

    cfg = {"experiment": "p9_word_faithfulness", "task": "word_faithfulness",
           "protocol": "docs/word-highlight-protocol.md", "population": f"reports/live_fever/{args.set}.scored.jsonl",
           "k": TOP_K, "n_random": N_RANDOM, "min_tokens": MIN_TOKENS, "seed": SEED, "models": [LIVE_NLI, LIVE_PARTNER]}
    inputs_sha = sha256_file(src)
    protocol_sha = sha256_file(PROTOCOL)
    config_hash = sha256_bytes(canonical_json(cfg) + inputs_sha.encode() + protocol_sha.encode())[:12]
    doc = {"config_hash": config_hash, "experiment": cfg["experiment"], "task": cfg["task"],
           "created_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git": git_info(), "env": env_info(),
           "seed": SEED, "seeded_libraries": seeded,
           "inputs": {"config": cfg, "population_sha256": inputs_sha, "protocol_sha256": protocol_sha},
           "population": {"n_with_shown_verdict": len(claims), "fewer_than_6_words": skipped,
                          "fewer_than_3_helpful_words": no_top, "n_scored": len(scored)},
           "metrics": metrics, "per_claim": scored}
    write_json(ROOT / "results" / f"{config_hash}.json", doc)
    print(f"written results/{config_hash}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
