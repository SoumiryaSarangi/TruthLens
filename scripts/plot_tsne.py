"""The cross-lingual embedding figure (FR-27, P1).

    python scripts/plot_tsne.py

Writes docs/figures/tsne_parallel_claims.png and a JSON of the numbers beside
it, because a figure nobody can check is decoration.

LaBSE only. `CLAUDE.md` restricts LaBSE to bitext alignment and this plot, and
this is exactly the bitext-alignment question: does a claim and its own
romanization land in the same place?

## Three sources, because each answers a different half of the question

  dakshina    The same sentence in native script and romanized, for hi and pa.
              A true parallel set, thousands of pairs, but ELICITED -- annotators
              asked to romanize Wikipedia text, so the spelling is tidier than
              real typing.

  handtyped   The 33 Punjabi forwards whose writer typed the same message twice,
              once in Latin letters and once in Gurmukhi. Real informal typing.
              Small, and the whole point: if these scatter further apart than
              the Dakshina pairs, the gap between elicited and real romanization
              is visible rather than argued.

  multiclaim  Posts in different languages that a fact-checker matched to the
              SAME fact-check. Not translations -- genuinely different posts
              making the same claim -- which is the relation the product
              actually needs. Only 17 such groups exist in dev+test, so this is
              an illustration, not a measurement.

The distance numbers printed and saved are what the report should quote. The
picture is for the reader; t-SNE distances are not metric and no conclusion
should rest on how far apart two dots look.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_json  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402

DAKSHINA = Path("data/raw/dakshina/extracted")
FIGURES = Path("docs/figures")
OUT_PNG = FIGURES / "tsne_parallel_claims.png"
OUT_JSON = FIGURES / "tsne_parallel_claims.json"


def dakshina_pairs(lang: str, limit: int) -> list[tuple[str, str]]:
    """(native, romanized) for the same sentence. Dakshina's DEV half."""
    base = DAKSHINA / lang
    native_path = base / f"{lang}.romanized.rejoined.dev.native.txt"
    roman_path = base / f"{lang}.romanized.rejoined.dev.roman.txt"
    if not native_path.is_file() or not roman_path.is_file():
        return []
    native = native_path.read_text(encoding="utf-8").splitlines()
    roman = roman_path.read_text(encoding="utf-8").splitlines()
    pairs = [(n.strip(), r.strip()) for n, r in zip(native, roman, strict=False)
             if len(n.strip()) > 30 and len(r.strip()) > 30]
    rng = random.Random(SEED)
    rng.shuffle(pairs)
    return pairs[:limit]


def handtyped_pairs() -> list[tuple[str, str]]:
    """(Gurmukhi, romanized) for the hand-typed forwards that carry both."""
    gold_path = Path("data/gold/handtyped_dev_translit.jsonl")
    text_path = Path("data/interim/handtyped/dev.jsonl")
    if not gold_path.is_file() or not text_path.is_file():
        return []
    texts = {r["uid"]: r["text"] for r in load_jsonl(text_path)}
    return [(r["reference"], texts[r["uid"]])
            for r in load_jsonl(gold_path) if r["uid"] in texts]


def multiclaim_groups() -> list[tuple[str, str, str]]:
    """(text, lang, group) for posts sharing a fact-check across languages."""
    rows: dict[str, dict] = {}
    texts: dict[str, str] = {}
    gold: dict[str, list[str]] = {}
    for split in ("dev", "test"):
        split_path = Path(f"data/splits/multiclaim/{split}.jsonl")
        gold_path = Path(f"data/gold/multiclaim_{split}_retrieval.jsonl")
        text_path = Path(f"data/interim/multiclaim/{split}.jsonl")
        if not (split_path.is_file() and gold_path.is_file() and text_path.is_file()):
            continue
        rows.update({r["uid"]: r for r in load_jsonl(split_path)})
        texts.update({r["uid"]: r["text"] for r in load_jsonl(text_path)})
        gold.update({r["uid"]: r["relevant_ids"] for r in load_jsonl(gold_path)})

    by_fc: dict[str, list[str]] = {}
    for uid, fcs in gold.items():
        for fc in fcs:
            by_fc.setdefault(fc, []).append(uid)

    out = []
    for fc, uids in by_fc.items():
        if len({rows[u]["lang"] for u in uids if u in rows}) < 2:
            continue
        for uid in uids:
            if uid in rows and texts.get(uid):
                out.append((texts[uid], rows[uid]["lang"], fc))
    return out


def cosine_pairs(vectors_a: np.ndarray, vectors_b: np.ndarray) -> np.ndarray:
    """Row-wise cosine. Vectors arrive L2-normalised from the encoder."""
    return np.sum(vectors_a * vectors_b, axis=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/plot_tsne.py")
    parser.add_argument("--per-lang", type=int, default=150,
                        help="Dakshina pairs per language")
    parser.add_argument("--perplexity", type=float, default=30.0)
    args = parser.parse_args(argv)
    set_all_seeds(SEED)

    from retrieval.encoders import build_encoder

    encoder = build_encoder("labse")
    points: list[dict] = []
    summary: dict[str, dict] = {}

    for lang in ("hi", "pa"):
        pairs = dakshina_pairs(lang, args.per_lang)
        if not pairs:
            print(f"  no Dakshina for {lang}")
            continue
        native = encoder.encode([p[0] for p in pairs])
        roman = encoder.encode([p[1] for p in pairs])
        sims = cosine_pairs(native, roman)
        summary[f"dakshina_{lang}"] = {
            "n": len(pairs), "mean_cosine": float(sims.mean()),
            "median_cosine": float(np.median(sims)), "std": float(sims.std()),
        }
        print(f"  dakshina {lang}: n={len(pairs)} mean cosine(native, romanized) "
              f"= {sims.mean():.4f}")
        for i in range(len(pairs)):
            points.append({"vec": native[i], "lang": lang, "script": "native",
                           "source": "dakshina", "group": f"dk-{lang}-{i}"})
            points.append({"vec": roman[i], "lang": lang, "script": "romanized",
                           "source": "dakshina", "group": f"dk-{lang}-{i}"})

    pairs = handtyped_pairs()
    if pairs:
        native = encoder.encode([p[0] for p in pairs])
        roman = encoder.encode([p[1] for p in pairs])
        sims = cosine_pairs(native, roman)
        summary["handtyped_pa"] = {
            "n": len(pairs), "mean_cosine": float(sims.mean()),
            "median_cosine": float(np.median(sims)), "std": float(sims.std()),
        }
        print(f"  handtyped pa: n={len(pairs)} mean cosine(native, romanized) "
              f"= {sims.mean():.4f}")
        for i in range(len(pairs)):
            points.append({"vec": native[i], "lang": "pa", "script": "native",
                           "source": "handtyped", "group": f"ht-{i}"})
            points.append({"vec": roman[i], "lang": "pa", "script": "romanized",
                           "source": "handtyped", "group": f"ht-{i}"})

    groups = multiclaim_groups()
    if groups:
        vectors = encoder.encode([g[0] for g in groups])
        summary["multiclaim_crosslingual"] = {
            "n_posts": len(groups),
            "n_groups": len({g[2] for g in groups}),
        }
        print(f"  multiclaim: {len(groups)} posts in "
              f"{len({g[2] for g in groups})} cross-lingual groups")
        for i, (_, lang, fc) in enumerate(groups):
            points.append({"vec": vectors[i], "lang": lang, "script": "claim",
                           "source": "multiclaim", "group": f"mc-{fc}"})

    if not points:
        print("nothing to plot; run scripts/download_models.py and make data first")
        return 2

    matrix = np.vstack([p["vec"] for p in points])
    print(f"\nprojecting {matrix.shape[0]} vectors with t-SNE")

    from sklearn.manifold import TSNE

    coords = TSNE(
        n_components=2, perplexity=min(args.perplexity, (len(points) - 1) / 3),
        init="pca", random_state=SEED, max_iter=1000,
    ).fit_transform(matrix)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    styles = {
        ("hi", "native"): ("#1f77b4", "o", "Hindi, Devanagari"),
        ("hi", "romanized"): ("#aec7e8", "^", "Hindi, romanized"),
        ("pa", "native"): ("#d62728", "o", "Punjabi, Gurmukhi"),
        ("pa", "romanized"): ("#ff9896", "^", "Punjabi, romanized"),
        ("en", "claim"): ("#2ca02c", "s", "English claim"),
        ("hi", "claim"): ("#9467bd", "s", "Hindi claim"),
        ("pa", "claim"): ("#8c564b", "s", "Punjabi claim"),
    }
    for key, (colour, marker, label) in styles.items():
        idx = [i for i, p in enumerate(points) if (p["lang"], p["script"]) == key]
        if idx:
            axes[0].scatter(coords[idx, 0], coords[idx, 1], c=colour, marker=marker,
                            s=18, alpha=0.7, label=label, linewidths=0)
    axes[0].set_title("LaBSE embedding space: language and script")
    axes[0].legend(fontsize=8, loc="best")
    axes[0].set_xticks([])
    axes[0].set_yticks([])

    # Right panel: join each parallel pair, so the question the figure asks --
    # does a claim sit next to its own romanization? -- is answered by the
    # length of the lines rather than by squinting at colours.
    by_group: dict[str, list[int]] = {}
    for i, p in enumerate(points):
        by_group.setdefault(p["group"], []).append(i)
    for group, idx in by_group.items():
        if len(idx) < 2:
            continue
        colour = "#d62728" if group.startswith("ht-") else "#999999"
        width = 1.0 if group.startswith("ht-") else 0.3
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                axes[1].plot(coords[[idx[a], idx[b]], 0], coords[[idx[a], idx[b]], 1],
                             c=colour, lw=width, alpha=0.5, zorder=1)
    axes[1].scatter(coords[:, 0], coords[:, 1], c="#333333", s=6, alpha=0.5, zorder=2)
    axes[1].set_title("Each line joins the same content in two scripts\n"
                      "(red = hand-typed forwards, grey = Dakshina / MultiClaim)")
    axes[1].set_xticks([])
    axes[1].set_yticks([])

    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"wrote {OUT_PNG}")

    write_json(OUT_JSON, {
        "note": "t-SNE distances are not metric. Quote the cosine figures, not "
                "the picture.",
        "encoder": "sentence-transformers/LaBSE",
        "seed": SEED,
        "perplexity": args.perplexity,
        "n_points": len(points),
        "cosine_similarity_between_parallel_pairs": summary,
    })
    print(f"wrote {OUT_JSON}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
