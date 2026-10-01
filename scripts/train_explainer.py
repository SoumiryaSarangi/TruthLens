"""Fine-tune IndicBART + LoRA to explain verdicts (Phase 6, FR-15, decision D6).

    python scripts/train_explainer.py

Input: claim </s> verdict </s> [1] evidence ... </s> <2en>; target: the claim's
AVeriTeC justification with its references to "the QA pairs" removed
(`generation.indicbart.clean_justification`).

**Train claims only, by split membership.** The local AVeriTeC test split is 307
claims held out of the public train.json, so iterating train.json would train
on test. Membership comes from the frozen `data/splits/averitec/train.jsonl`.

**Evidence is the gold QA**, which is what each justification was written
against. Served, the model reads retrieved passages instead; the NLI gate exists
for exactly that gap, and the evals measure both inputs.

LoRA rather than full fine-tuning: AdamW state for 244M parameters is ~3.9 GB
on a ~4.9 GiB card before a single activation.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.seeds import SEED, set_all_seeds  # noqa: E402
from generation.explain_data import examples  # noqa: E402
from generation.indicbart import (  # noqa: E402
    BASE_MODEL,
    DEFAULT_ADAPTER,
    LANG_TAG,
    MAX_SOURCE,
    MAX_TARGET,
    encode_source,
    source_text,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/train_explainer.py")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--out", default=str(DEFAULT_ADAPTER))
    args = ap.parse_args(argv)
    set_all_seeds(SEED)

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AlbertTokenizer, MBartForConditionalGeneration

    data = examples("train")
    print(f"explainer: {len(data)} train claims")
    tok = AlbertTokenizer.from_pretrained(BASE_MODEL, do_lower_case=False,
                                          use_fast=False, keep_accents=True)
    pad = tok._convert_token_to_id_with_added_voc("<pad>")
    eos = tok._convert_token_to_id_with_added_voc("</s>")
    encoded = []
    for ex in data:
        src = encode_source(tok, source_text(ex["claim"], ex["verdict"], ex["evidence"]),
                            MAX_SOURCE)
        tgt = tok(f"{LANG_TAG} {ex['target']}", add_special_tokens=False).input_ids
        tgt = [*tgt[:MAX_TARGET - 1], eos]
        encoded.append((src, tgt))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = MBartForConditionalGeneration.from_pretrained(BASE_MODEL)
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM, r=args.lora_r, lora_alpha=args.lora_alpha,
        lora_dropout=0.1, target_modules=["q_proj", "k_proj", "v_proj", "out_proj"]))
    model.to(device).train()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  trainable {trainable:,}")

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    # bf16, not fp16: the first run under fp16 autocast went to NaN loss in epoch
    # 1 -- mBART-family models overflow fp16's range. bf16 keeps fp32's exponent,
    # so it needs no loss scaler, and the RTX 4050 (Ada) supports it.
    use_amp = device == "cuda" and torch.cuda.is_bf16_supported()
    rng = random.Random(SEED)
    started = time.time()

    def batchify(items):
        width_s = max(len(s) for s, _ in items)
        width_t = max(len(t) for _, t in items)
        src = [s + [pad] * (width_s - len(s)) for s, _ in items]
        tgt = [t + [pad] * (width_t - len(t)) for _, t in items]
        src_t = torch.tensor(src, device=device)
        tgt_t = torch.tensor(tgt, device=device)
        labels = tgt_t[:, 1:].clone()
        labels[labels == pad] = -100
        return src_t, (src_t != pad).long(), tgt_t[:, :-1], labels

    for epoch in range(args.epochs):
        order = list(range(len(encoded)))
        rng.shuffle(order)
        total, steps = 0.0, 0
        for start in range(0, len(order), args.batch_size):
            src, mask, dec_in, labels = batchify([encoded[i] for i in
                                                  order[start:start + args.batch_size]])
            with torch.autocast(device_type=device, dtype=torch.bfloat16, enabled=use_amp):
                loss = model(input_ids=src, attention_mask=mask,
                             decoder_input_ids=dec_in, labels=labels).loss
            if not torch.isfinite(loss):
                # Refused at the first bad step, not after four epochs of NaN.
                print(f"non-finite loss at epoch {epoch + 1}, step {steps + 1}; stopping")
                return 1
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += loss.item()
            steps += 1
        print(f"  epoch {epoch + 1}/{args.epochs}  loss {total / steps:.4f}  "
              f"({(time.time() - started) / 60:.1f} min)", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    peak = torch.cuda.max_memory_allocated() / 2**30 if device == "cuda" else 0.0
    (out / "training.json").write_text(json.dumps({
        "base_model": BASE_MODEL, "seed": SEED, "epochs": args.epochs,
        "batch_size": args.batch_size, "lr": args.lr, "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha, "n_train": len(encoded),
        "precision": "bf16 autocast" if use_amp else "fp32",
        "evidence": "gold QA", "targets": "cleaned AVeriTeC justifications",
        "peak_vram_gib": round(peak, 3),
        "minutes": round((time.time() - started) / 60, 1)}, indent=2), encoding="utf-8")
    print(f"wrote {out}  peak VRAM {peak:.2f} GiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
