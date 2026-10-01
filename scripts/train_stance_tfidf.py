"""Train the TF-IDF + LR stance baseline and its claim-only twin (FR-10).

    python scripts/train_stance_tfidf.py              # both arms

Reads the averitec_stance TRAIN split only. The split inherits its membership
from the frozen AVeriTeC splits, so no claim held out to dev or test can reach a
training row. Writes gitignored `data/interim/models/stance_{tfidf,
tfidf_claimonly}.joblib`. CPU, about a minute each.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from stance.tfidf import MODELS, build_pipeline  # noqa: E402

SPLIT = Path("data/splits/averitec_stance/train.jsonl")
INTERIM = Path("data/interim/averitec_stance/train.jsonl")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/train_stance_tfidf.py")
    ap.add_argument("--arm", choices=["both", "full", "claimonly"], default="both")
    args = ap.parse_args(argv)
    set_all_seeds(SEED)

    import joblib

    labels = {r["uid"]: r["label"] for r in load_jsonl(SPLIT)}
    rows = [r for r in load_jsonl(INTERIM) if r["uid"] in labels]
    x = [{"claim": r["claim"], "evidence": r["evidence"]} for r in rows]
    y = [labels[r["uid"]] for r in rows]
    print(f"{len(rows)} training pairs over "
          f"{len({r['claim'] for r in rows})} claims: {dict(collections.Counter(y))}")

    arms = {"full": False, "claimonly": True}
    if args.arm != "both":
        arms = {args.arm: arms[args.arm]}
    MODELS.mkdir(parents=True, exist_ok=True)
    for arm, claim_only in arms.items():
        started = time.time()
        model = build_pipeline(claim_only).fit(x, y)
        name = "stance_tfidf_claimonly" if claim_only else "stance_tfidf"
        joblib.dump(model, MODELS / f"{name}.joblib")
        (MODELS / f"{name}.json").write_text(json.dumps({
            "arm": arm, "claim_only": claim_only, "seed": SEED, "n_train": len(rows),
            "label_counts": dict(collections.Counter(y)),
            "seconds": round(time.time() - started, 1),
        }, indent=2), encoding="utf-8")
        print(f"  {name}: {time.time() - started:.1f}s -> {MODELS / name}.joblib")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
