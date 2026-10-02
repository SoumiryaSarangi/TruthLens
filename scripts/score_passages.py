"""Stance probabilities for a cached passages file (Phase 6, decisions D1-D2).

    python scripts/score_passages.py --passages results/preds/p6_passages_train.jsonl \
        --stance xlmr --folds --out results/preds/p6_scored_train_xlmr.jsonl
    python scripts/score_passages.py --passages results/preds/p6_passages_dev.jsonl \
        --stance xlmr --out results/preds/p6_scored_dev_xlmr.jsonl

`--folds` is cross-fitting: each TRAIN claim is scored by `stance_<impl>_fold<f>`,
the model trained without its fold (`stance/folds.py`), so the aggregator never
learns from stance outputs on claims the stance model memorised. Dev and test
claims are scored by the model trained on all of train.

Scoring a train claim with a model that saw it is REFUSED unless
`--allow-in-fold` -- which exists only to measure how much that leak would have
inflated the features, never to train on.

This produces model outputs, not metrics; nothing here is scored.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import test_guard  # noqa: E402
from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from common.seeds import set_all_seeds  # noqa: E402
from pipeline import registry  # noqa: E402
from stance.folds import N_FOLDS, fold_of  # noqa: E402

MODELS = Path("data/interim/models")
TRAINED = ("xlmr", "xlmr_claimonly", "bilstm")


def build(stance: str, fold: int | None):
    """The stance model for one fold, or the full model when `fold` is None."""
    if stance not in TRAINED:
        return registry.build("stance", stance)
    name = f"stance_{stance}" + ("" if fold is None else f"_fold{fold}")
    path = MODELS / name
    if not path.exists():
        how = f" with --fold {fold}" if fold is not None else ""
        raise SystemExit(f"no stance model at {path}; train it first{how}.")
    kwargs = {"model_dir": path} if stance == "bilstm" else {"adapter": path}
    return registry.build("stance", stance, **kwargs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/score_passages.py")
    ap.add_argument("--passages", required=True)
    ap.add_argument("--stance", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--folds", action="store_true", help="cross-fit train claims")
    ap.add_argument("--n-folds", type=int, default=N_FOLDS)
    ap.add_argument("--allow-in-fold", action="store_true",
                    help="score train claims with the full model -- ONLY to measure "
                         "the leak cross-fitting prevents")
    args = ap.parse_args(argv)
    set_all_seeds()

    rows = list(load_jsonl(args.passages))
    try:
        test_guard.require_allowed(None, rows, what="stance scoring")
    except test_guard.TestSplitLocked as exc:
        raise SystemExit(f"REFUSED: {exc}") from None
    # By the uid's split, NOT the source_id: the 307 test claims are carved from
    # AVeriTeC's train.json, so their source_ids say train.json too.
    on_train = [r for r in rows if test_guard.uid_split(r["uid"]) == "train"]
    trained = args.stance in TRAINED
    if args.folds and len(on_train) != len(rows):
        raise SystemExit("--folds applies to train claims only; this file mixes splits.")
    if trained and on_train and not args.folds and not args.allow_in_fold:
        raise SystemExit(
            f"REFUSED: {len(on_train)} train claims would be scored by the {args.stance} "
            "model trained on them. Pass --folds (cross-fit), or --allow-in-fold to "
            "measure that leak deliberately."
        )

    groups: dict[int | None, list[dict]] = defaultdict(list)
    for r in rows:
        f = fold_of(r["source_id"], args.n_folds) if (args.folds and trained) else None
        groups[f].append(r)

    out: dict[str, dict] = {}
    started = time.time()
    for fold, members in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0])):
        model = build(args.stance, fold)
        for r in members:
            texts = [p["text"] for p in r["passages"]]
            results = model.label(r["claim"], texts) if texts else []
            out[r["uid"]] = {
                "uid": r["uid"], "source_id": r["source_id"], "stance": args.stance,
                "fold": fold, "probs": [res.probs for res in results],
                "dense": [p.get("dense_score") for p in r["passages"]],
            }
        print(f"  fold {fold}: {len(members)} claims  "
              f"({(time.time() - started) / 60:.1f} min)", flush=True)
        del model
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass

    write_jsonl(Path(args.out), [out[r["uid"]] for r in rows])
    print(f"wrote {len(out)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
