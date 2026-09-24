"""Fine-tune XLM-R-base + LoRA for check-worthiness (FR-6).

    python scripts/train_checkworthy.py

Writes a LoRA adapter to gitignored `data/interim/models/checkworthy_xlmr/`.

## Why this exists as a separate model

Phase 3 first tried deriving check-worthiness from the span model: if it finds
no claim token, there is no claim. Measured on the 100 hand-typed forwards, that
rejected **0 of 15** no-claim messages while getting 70/70 of the
straightforward positives right.

The reason is structural, not a tuning problem. The span model trains on
X-CLAIM, where **every post contains a claim** -- it has never seen a message
that does not, so "did I find claim tokens" is a question it has no way to
answer in the negative. A model cannot learn a class it was never shown.

So this one trains on `xclaim_cw`, the derived set built exactly for it: the
out-of-span remainder of a post whose claim is a strict subset is a message that
demonstrably contains no claim. 3,443 negatives in train.

## What the number will and will not mean

The derived negatives are fragments of posts that DID contain a claim, so they
share vocabulary and register with their own positives. That makes this set
easier than reality in one direction, and possibly harder in another -- a
fragment reads as truncated in a way a real greeting does not. Either way the
100 hand-typed forwards are the honest test, and they are `dev` for a different
dataset, so nothing here touches them.

Sequence classification, not token classification: the question is about the
whole message, and FR-6 short-circuits the whole message.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from data.labels import CHECKWORTHY_BINARY  # noqa: E402

BASE_MODEL = "xlm-roberta-base"
MODELS = Path("data/interim/models")
SPLITS = Path("data/splits/xclaim_cw")
INTERIM = Path("data/interim/xclaim_cw")

LABEL_TO_ID = {label: i for i, label in enumerate(CHECKWORTHY_BINARY)}
ID_TO_LABEL = dict(enumerate(CHECKWORTHY_BINARY))


def load_split(split: str) -> list[dict]:
    texts = {r["uid"]: r["text"] for r in load_jsonl(INTERIM / f"{split}.jsonl")}
    out = []
    for row in load_jsonl(SPLITS / f"{split}.jsonl"):
        text = texts.get(row["uid"], "").strip()
        if text and row.get("label") in LABEL_TO_ID:
            out.append({"text": text, "label": LABEL_TO_ID[row["label"]],
                        "lang": row["lang"]})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/train_checkworthy.py")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    args = parser.parse_args(argv)
    set_all_seeds(SEED)

    train = load_split("train")
    counts = {label: sum(1 for e in train if e["label"] == i)
              for label, i in LABEL_TO_ID.items()}
    print(f"checkworthy_xlmr: {len(train)} train rows, {counts}")
    if not train:
        print("no training rows; run `python scripts/build_splits.py build "
              "--dataset xclaim_cw` first")
        return 2

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    base = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(CHECKWORTHY_BINARY),
        id2label=ID_TO_LABEL, label2id=LABEL_TO_ID,
    )
    model = get_peft_model(base, LoraConfig(
        task_type=TaskType.SEQ_CLS, r=args.lora_r, lora_alpha=args.lora_alpha,
        lora_dropout=0.1, bias="none",
        target_modules=["query", "key", "value"],
        modules_to_save=["classifier"],
    ))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  trainable {trainable:,}")

    encoded = tokenizer([e["text"] for e in train], truncation=True,
                        max_length=args.max_length, padding=False)
    encoded["labels"] = [e["label"] for e in train]

    class Dataset(torch.utils.data.Dataset):
        def __len__(self):
            return len(encoded["input_ids"])

        def __getitem__(self, i):
            return {k: v[i] for k, v in encoded.items()}

    batch_size = args.batch_size
    started = time.time()
    out_dir = MODELS / "checkworthy_xlmr"
    while True:
        try:
            Trainer(
                model=model,
                args=TrainingArguments(
                    output_dir=str(out_dir / "_hf"),
                    num_train_epochs=args.epochs,
                    per_device_train_batch_size=batch_size,
                    learning_rate=args.lr,
                    fp16=torch.cuda.is_available(),
                    logging_steps=100, save_strategy="no", report_to=[],
                    seed=SEED, dataloader_num_workers=0,
                ),
                train_dataset=Dataset(),
                data_collator=DataCollatorWithPadding(tokenizer),
            ).train()
            break
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if batch_size <= 1:
                print("OOM at batch size 1. Next lever is gradient checkpointing, "
                      "then 4-bit -- not a smaller model.")
                return 1
            batch_size //= 2
            print(f"  OOM -> halving batch size to {batch_size}")

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    peak = torch.cuda.max_memory_allocated() / 2**30 if torch.cuda.is_available() else 0.0
    (out_dir / "training.json").write_text(json.dumps({
        "base_model": BASE_MODEL, "seed": SEED, "epochs": args.epochs,
        "batch_size": batch_size, "lr": args.lr, "max_length": args.max_length,
        "lora_r": args.lora_r, "lora_alpha": args.lora_alpha,
        "n_train": len(train), "label_counts": counts,
        "peak_vram_gib": round(peak, 3),
        "minutes": round((time.time() - started) / 60, 1),
    }, indent=2), encoding="utf-8")
    print(f"wrote {out_dir}\n  peak VRAM {peak:.2f} GiB, batch {batch_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
