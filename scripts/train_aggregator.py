"""Train the learned verdict aggregator (Phase 6, FR-11 and FR-13).

    python scripts/train_aggregator.py --stance xlmr \
        --train results/preds/p6_scored_train_xlmr.jsonl \
        --dev results/preds/p6_scored_dev_xlmr.jsonl --k 10

Logistic regression (multinomial, standardised features, balanced class weights
because the target is macro-F1 and Conflicting is rare) on the CROSS-FITTED
stance outputs for AVeriTeC train claims; then one temperature, fitted on dev by
negative log-likelihood (FR-13). Writes
`data/interim/models/aggregator_<stance>[_k<k>]/model.joblib` and
`training.json`.

Nothing here is a reported number. Macro-F1 and ECE come only from the harness,
on predictions the orchestrator writes through this artifact. The dev NLL below
is the temperature's fitting objective, logged so a degenerate fit is visible.

The temperature is fitted and its ECE scored on the same 500 dev claims; with one
parameter the optimism is small but not zero, and the out-of-sample check is the
test split's ECE in Phase 7, which this script never sees.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from pipeline.aggregate import (  # noqa: E402
    MODELS,
    SOURCES,
    VERDICTS,
    feature_names,
    multi_features,
    softmax,
)

SPLITS = Path("data/splits/averitec")


def load(scored_path: str, split: str, k: int,
         sources: tuple[str, ...] = ("",)) -> tuple[list[list[float]], list[str], list[dict]]:
    gold = {r["uid"]: r["label"] for r in load_jsonl(SPLITS / f"{split}.jsonl")}
    rows = list(load_jsonl(scored_path))
    missing = [r["uid"] for r in rows if r["uid"] not in gold]
    if missing:
        raise SystemExit(f"{len(missing)} scored rows are not in the {split} split, "
                         f"e.g. {missing[:3]}")
    return ([multi_features(r["probs"], r["dense"], k=k, sources=sources) for r in rows],
            [gold[r["uid"]] for r in rows], rows)


def nll(logits: list[list[float]], y: list[str], temperature: float) -> float:
    total = 0.0
    for row, label in zip(logits, y, strict=True):
        p = softmax(row, temperature)[VERDICTS.index(label)]
        total -= math.log(max(p, 1e-12))
    return total / len(y)


def fit_temperature(logits: list[list[float]], y: list[str]) -> float:
    """Golden-section search over log T in [-3, 3]: one convex 1-D problem."""
    lo, hi = -3.0, 3.0
    g = (math.sqrt(5) - 1) / 2
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    fa, fb = nll(logits, y, math.exp(a)), nll(logits, y, math.exp(b))
    for _ in range(60):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - g * (hi - lo)
            fa = nll(logits, y, math.exp(a))
        else:
            lo, a, fa = a, b, fb
            b = lo + g * (hi - lo)
            fb = nll(logits, y, math.exp(b))
    return math.exp((lo + hi) / 2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/train_aggregator.py")
    ap.add_argument("--stance", required=True)
    ap.add_argument("--train", required=True, help="cross-fitted scored passages, train")
    ap.add_argument("--dev", required=True, help="scored passages, dev")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--C", type=float, default=1.0)
    ap.add_argument("--name", default=None)
    ap.add_argument("--read", default="base",
                    help="comma-separated stance sources the aggregator reads: base "
                         "(the plain keys) and/or xlmr (the combined stage's prior)")
    args = ap.parse_args(argv)
    set_all_seeds(SEED)

    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    started = time.time()
    sources = tuple(SOURCES[name] for name in args.read.split(","))
    x_train, y_train, train_rows = load(args.train, "train", args.k, sources)
    folds = {r.get("fold") for r in train_rows}
    if args.stance in ("xlmr", "xlmr_claimonly", "bilstm", "xlmr_nli") and None in folds:
        raise SystemExit("REFUSED: the train file was not cross-fitted (some rows have "
                         "no fold). Score it with `score_passages.py --folds`.")
    x_dev, y_dev, _ = load(args.dev, "dev", args.k, sources)
    unknown = set(y_train) - set(VERDICTS)
    if unknown:
        raise SystemExit(f"labels {unknown} are not aggregator classes {VERDICTS}")

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=args.C, class_weight="balanced", max_iter=5000,
                           random_state=SEED),
    )
    model.fit(x_train, y_train)

    order = list(model.classes_)
    dev_logits = [[float(dict(zip(order, row, strict=True)).get(v, -1e9)) for v in VERDICTS]
                  for row in model.decision_function(x_dev)]
    temperature = fit_temperature(dev_logits, y_dev)

    name = args.name or f"aggregator_{args.stance}" + ("" if args.k == 10 else f"_k{args.k}")
    out_dir = MODELS / name
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feature_names(sources), "stance": args.stance,
                 "sources": sources, "k": args.k, "temperature": temperature,
                 "classes": VERDICTS},
                out_dir / "model.joblib")
    (out_dir / "training.json").write_text(json.dumps({
        "stance": args.stance, "reads": args.read, "k": args.k, "C": args.C, "seed": SEED,
        "n_train": len(y_train), "train_label_counts": dict(Counter(y_train)),
        "n_dev_for_temperature": len(y_dev), "temperature": round(temperature, 4),
        "dev_nll_T1": round(nll(dev_logits, y_dev, 1.0), 4),
        "dev_nll_fitted": round(nll(dev_logits, y_dev, temperature), 4),
        "cross_fitted_train": None not in folds,
        "seconds": round(time.time() - started, 1),
    }, indent=2), encoding="utf-8")
    print(f"wrote {out_dir}  T={temperature:.3f}  n_train={len(y_train)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
