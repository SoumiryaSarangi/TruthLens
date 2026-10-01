"""Where the explainer looks while it writes: cross-attention over the evidence.

    python scripts/plot_explainer_attention.py

Unit IV asks for seq2seq with attention, and the reason IndicBART was chosen
over a decoder-only model is that its cross-attention is over the actual
evidence passages, so this figure means something (docs/build-plan.md, Phase 6).

Writes docs/figures/explainer_attention.png and a JSON of the numbers beside
it, as `plot_tsne.py` does -- a figure nobody can check is decoration.

**The claim is chosen by rule, not by eye:** the first AVeriTeC dev claim, in
split order, with at least three gold QA passages and a source under 300
tokens. Cherry-picking the prettiest heatmap would make the figure a claim
about one example dressed up as a claim about the model.

Attention is averaged over all decoder layers and heads, teacher-forced on the
model's own beam output. Attention is not explanation (Jain & Wallace, 2019):
the figure shows what the decoder attended to, not why it wrote what it wrote.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import write_json  # noqa: E402
from common.seeds import set_all_seeds  # noqa: E402
from generation.explain_data import examples  # noqa: E402
from generation.indicbart import (  # noqa: E402
    IndicBARTExplainer,
    encode_source,
    source_text,
)

FIGURES = Path("docs/figures")
OUT_PNG = FIGURES / "explainer_attention.png"
OUT_JSON = FIGURES / "explainer_attention.json"


def segments(tok, claim: str, verdict: str, passages: list[str],
             n_source: int) -> list[tuple[str, int, int]]:
    """(label, start, end) token ranges covering the WHOLE encoder input.

    The trailing `</s> <2en>` gets its own column: decoders park much of their
    attention on such tokens, and a figure that left them out would show a
    fraction of the attention and let the reader assume it was all of it.
    Passages cut off by truncation are clipped to what the encoder saw.
    """
    parts = [("claim", claim.strip()), ("verdict", f"</s> {verdict} </s>")]
    parts += [(f"[{i}]", f"[{i}] {p.strip()}") for i, p in enumerate(passages, start=1)]
    body_end = n_source - 2
    out, cursor = [], 0
    for label, text in parts:
        n = len(tok(text, add_special_tokens=False).input_ids)
        start, end = min(cursor, body_end), min(cursor + n, body_end)
        if end > start:
            out.append((label, start, end))
        cursor += n
    out.append(("</s> <2en>", body_end, n_source))
    return out


def main() -> int:
    set_all_seeds()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import torch

    explainer = IndicBARTExplainer(attn_implementation="eager")
    tok, model = explainer._load()
    chosen = None
    for ex in examples("dev"):
        if len(ex["evidence"]) < 3:
            continue
        ids = encode_source(tok, source_text(ex["claim"], ex["verdict"], ex["evidence"][:5]))
        if len(ids) < 300:
            chosen = (ex, ids)
            break
    if chosen is None:
        raise SystemExit("no dev claim meets the selection rule")
    ex, src_ids = chosen
    passages = ex["evidence"][:5]
    text = explainer.generate(ex["claim"], ex["verdict"], passages, decoding="beam")

    special = tok._convert_token_to_id_with_added_voc
    tgt = [special("<2en>"), *tok(text, add_special_tokens=False).input_ids, special("</s>")]
    device = next(model.parameters()).device
    with torch.inference_mode():
        out = model(input_ids=torch.tensor([src_ids], device=device),
                    decoder_input_ids=torch.tensor([tgt[:-1]], device=device),
                    output_attentions=True)
    # (layers, batch, heads, tgt, src) -> mean over layers and heads -> (tgt, src)
    att = torch.stack(out.cross_attentions).float().mean(dim=(0, 2))[0].cpu().numpy()

    segs = segments(tok, ex["claim"], ex["verdict"], passages, len(src_ids))
    mass = [[float(att[t, s:e].sum()) for _, s, e in segs] for t in range(att.shape[0])]
    out_tokens = tok.convert_ids_to_tokens(tgt[1:])

    fig, ax = plt.subplots(figsize=(1.1 * len(segs) + 3, 0.28 * len(out_tokens) + 2))
    im = ax.imshow(mass, aspect="auto", cmap="Blues", vmin=0.0,
                   vmax=max(max(row) for row in mass))
    ax.set_xticks(range(len(segs)), [label for label, _, _ in segs])
    ax.set_yticks(range(len(out_tokens)), [t.replace("▁", "") for t in out_tokens],
                  fontsize=7)
    ax.set_xlabel("encoder input segment (claim, verdict, gold QA passages)")
    ax.set_ylabel("generated token")
    ax.set_title("IndicBART explainer: cross-attention mass per evidence segment\n"
                 "(mean over layers and heads; dev claim chosen by rule)", fontsize=9)
    fig.colorbar(im, ax=ax, label="share of attention")
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150)

    write_json(OUT_JSON, {
        "uid": ex["uid"], "claim": ex["claim"], "verdict": ex["verdict"],
        "passages": passages, "explanation": text,
        "segments": [label for label, _, _ in segs],
        "attention_mass_per_token": dict(zip(out_tokens, mass, strict=False)),
        "mean_mass_per_segment": {label: float(sum(row[i] for row in mass) / len(mass))
                                  for i, (label, _, _) in enumerate(segs)},
        "row_sums_min_max": [min(sum(r) for r in mass), max(sum(r) for r in mass)],
        "selection_rule": "first dev claim with >=3 gold QA passages and <300 source tokens",
        "caveat": "attention shows where the decoder looked, not why it wrote what it did",
    })
    print(f"wrote {OUT_PNG} and {OUT_JSON}\n  claim: {ex['claim'][:100]}\n  explanation: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
