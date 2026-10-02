"""The research contribution as one figure: native vs romanized, stage by stage.

    python scripts/plot_romanization_gap.py \
        --stage "Language ID (accuracy)=7f4d2e1ee058" \
        --stage "Claim matching (MRR)=3bebeaff50b0" \
        --stage "Claim span (token F1)=02c59ee296a0,f05dd5f44b16" \
        --out docs/figures/romanization_gap.png

Each `--stage` names one results file whose `native_vs_romanized` block has both
cells, or two (native run, romanized run) when the romanized rows are their own
split -- X-CLAIM's romanized posts are `x_claim_romanized`, scored separately on
the same posts. Values are read from those blocks as `make eval` wrote them;
nothing is computed. Every bar carries its n, because Punjabi cells are often
single digits and a bar without its denominator would overstate them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(run: str, lang: str, side: str) -> tuple[float | None, int]:
    doc = json.loads((ROOT / "results" / f"{run}.json").read_text(encoding="utf-8"))
    block = doc.get("native_vs_romanized", {}).get("by_lang", {}).get(lang, {})
    value = block.get(side)
    return value, int(block.get(f"n_{side}", 0) or 0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/plot_romanization_gap.py")
    ap.add_argument("--stage", action="append", required=True,
                    help='"label=run" or "label=native_run,romanized_run"')
    ap.add_argument("--out", default="docs/figures/romanization_gap.png")
    args = ap.parse_args(argv)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stages = []
    for spec in args.stage:
        label, _, runs = spec.partition("=")
        native_run, _, roman_run = runs.partition(",")
        stages.append((label, native_run, roman_run or native_run))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, lang, name in zip(axes, ("hi", "pa"), ("Hindi", "Punjabi"), strict=True):
        for i, (_label, native_run, roman_run) in enumerate(stages):
            for offset, (side, run, colour) in enumerate(
                    (("native", native_run, "#2b6cb0"), ("romanized", roman_run, "#dd6b20"))):
                value, n = cell(run, lang, side)
                x = i + (offset - 0.5) * 0.38
                if value is None:
                    ax.text(x, 0.02, "no data", ha="center", fontsize=7, rotation=90)
                    continue
                ax.bar(x, value, width=0.36, color=colour,
                       label=side if i == 0 else None)
                ax.text(x, value + 0.01, f"{value:.2f}\nn={n}", ha="center", fontsize=7)
        ax.set_xticks(range(len(stages)))
        ax.set_xticklabels([s[0] for s in stages], fontsize=8)
        ax.set_title(name)
        ax.set_ylim(0, 1.15)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.suptitle("Native script vs romanized input, per stage (higher is better)", fontsize=11)
    fig.tight_layout()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
