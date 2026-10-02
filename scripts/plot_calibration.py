"""The abstention curve (the headline figure) and the reliability diagram.

    python scripts/plot_calibration.py --run dev=164d2289c90b --run test=<hash>
        --majority dev=8350085fbc7f --majority test=<hash> --tau 0.3835

Reads only what `make eval` stored under `metrics.overall.calibration` in
results/<hash>.json -- the coverage curve, the reliability bins, the operating
point -- and draws it. It computes nothing; a number that is not in a results
file cannot appear in these figures.

CLAUDE.md: never show an accuracy without the majority baseline beside it. On
AVeriTeC always-Refuted scores 0.61 on dev, above the system's accuracy at full
coverage, so `--majority label=hash` (a run whose baseline is majority_class on
the same split) is required and drawn as a dotted line per split.

Writes docs/figures/abstention_curve.png and docs/figures/reliability.png.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"


def load(spec: str) -> tuple[str, dict, dict]:
    label, _, run = spec.partition("=")
    doc = json.loads((ROOT / "results" / f"{run}.json").read_text(encoding="utf-8"))
    overall = doc["metrics"]["overall"]
    if "calibration" not in overall:
        raise SystemExit(f"run {run} has no calibration block; score it with `calibration:`")
    return f"{label} ({run[:6]})", overall, doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/plot_calibration.py")
    ap.add_argument("--run", action="append", required=True,
                    help="label=config_hash, repeatable (e.g. dev=164d2289c90b)")
    ap.add_argument("--majority", action="append", required=True,
                    help="label=config_hash of a run scored against majority_class "
                         "on the same split; its baseline accuracy is drawn")
    ap.add_argument("--tau", type=float, default=None,
                    help="the served tau_abstain, marked on the curve")
    args = ap.parse_args(argv)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = [load(spec) for spec in args.run]
    FIGURES.mkdir(parents=True, exist_ok=True)

    fig, (ax_acc, ax_f1) = plt.subplots(1, 2, figsize=(11, 4.2))
    for label, overall, _doc in runs:
        curve = sorted(overall["calibration"]["coverage_curve"], key=lambda p: p["coverage"])
        cov = [p["coverage"] for p in curve]
        line, = ax_acc.plot(cov, [p["accuracy"] for p in curve], marker=".", label=label)
        ax_f1.plot(cov, [p["macro_f1"] for p in curve], marker=".", label=label,
                   color=line.get_color())
        point = overall["calibration"].get("at_tau") or overall["calibration"]["operating_point"]
        ax_acc.scatter([point["coverage"]], [point["selective_accuracy"]], s=60,
                       color=line.get_color(), edgecolor="black", zorder=5)
        ax_f1.scatter([point["coverage"]], [point["selective_macro_f1"]], s=60,
                      color=line.get_color(), edgecolor="black", zorder=5)
    for spec in args.majority:
        label, _, run = spec.partition("=")
        doc = json.loads((ROOT / "results" / f"{run}.json").read_text(encoding="utf-8"))
        if doc.get("baseline", {}).get("name") != "majority_class":
            raise SystemExit(f"run {run}'s baseline is not majority_class")
        acc = doc["baseline"]["metrics"]["accuracy"]
        ax_acc.axhline(acc, color="grey", ls=":", lw=1.2)
        ax_acc.annotate(f"always-Refuted, {label}: {acc:.2f}", (0.02, acc), fontsize=8,
                        color="dimgrey", xytext=(0, 3), textcoords="offset points")
    ax_acc.set_title("Accuracy on the claims answered")
    ax_f1.set_title("Macro-F1 on the claims answered")
    for ax in (ax_acc, ax_f1):
        ax.set_xlabel("coverage (share of claims the system answers)")
        ax.set_xlim(0, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    note = f"dots: tau_abstain {args.tau}" if args.tau is not None else "dots: operating point"
    fig.suptitle(f"Abstention: answering fewer claims, more of them right ({note})", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / "abstention_curve.png", dpi=150)

    fig, ax = plt.subplots(figsize=(5.2, 5))
    ax.plot([0, 1], [0, 1], color="grey", ls="--", lw=1, label="perfectly calibrated")
    for label, overall, _ in runs:
        bins = overall["calibration"]["reliability"]
        ax.plot([b["mean_confidence"] for b in bins], [b["accuracy"] for b in bins],
                marker="o", label=f"{label}, ECE {overall['ece']:.3f}")
        for b in bins:
            ax.annotate(f"{int(b['n'])}", (b["mean_confidence"], b["accuracy"]),
                        fontsize=7, xytext=(3, -9), textcoords="offset points")
    ax.set_xlabel("confidence (mean in bin)")
    ax.set_ylabel("accuracy in bin")
    ax.set_title("Reliability (numbers: claims per bin)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "reliability.png", dpi=150)
    print(f"wrote {FIGURES / 'abstention_curve.png'} and {FIGURES / 'reliability.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
