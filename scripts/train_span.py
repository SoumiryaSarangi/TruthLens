"""Fine-tune XLM-R-base + LoRA for claim span identification (FR-7).

    python scripts/train_span.py --arm joint
    python scripts/train_span.py --arm mono --lang pa
    python scripts/train_span.py --arm zeroshot          # train en+hi, test pa

The project's first fine-tuned model. Writes a LoRA adapter to gitignored
`data/interim/models/span_xlmr_{arm}/`, following the precedent set by
`roman_lid.joblib` and `word2vec.kv` -- no document stated a checkpoint policy
before this one.

## The ablation, and why it is worth three runs

`docs/build-plan.md`: X-CLAIM's own paper found joint multilingual training
beats zero-shot transfer. Replicating that deliberately is cheaper than
rediscovering it by accident, and on this data the comparison is sharp: Punjabi
has 249 training rows, so the monolingual Punjabi arm should be poor and the
joint arm should rescue it. If it does not, that is worth knowing before Phase 5
builds on the same backbone.

A fourth arm -- training on machine-translated English -- is in the build plan
and is NOT run here. `data/CLAUDE.md` deliberately never downloaded X-CLAIM's
`en2xx` files, precisely so they could not contaminate this comparison. An
absence with a recorded reason beats a silent gap.

## VRAM

~4.9 GiB usable on this card, not the 5.5 GB NFR-3 assumes -- Windows holds the
rest (`docs/environment.md`). If it will not fit, the order is: smaller batch,
then gradient checkpointing, then 4-bit. **Never a smaller model**, which would
change what the result means. `--batch-size` halves automatically on OOM.

Labels are the BIO tags the gold already uses. Subword tokens inherit the tag of
the word they start and are masked (-100) thereafter, so the loss is computed
once per word rather than once per subword -- otherwise a long word would count
more than a short one for no reason.
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
from data.labels import SPAN_BIO  # noqa: E402

BASE_MODEL = "xlm-roberta-base"
MODELS = Path("data/interim/models")
GOLD = Path("data/gold")
SPLITS = Path("data/splits/x_claim")

LABEL_TO_ID = {tag: i for i, tag in enumerate(SPAN_BIO)}
ID_TO_LABEL = dict(enumerate(SPAN_BIO))

ARM_TRAIN_LANGS = {
    "joint": ("en", "hi", "pa"),
    "zeroshot": ("en", "hi"),        # pa is held out entirely
}


def load_arm(arm: str, lang: str | None, split: str) -> list[dict]:
    """Gold rows for one ablation arm, filtered by the split's own language."""
    gold = {r["uid"]: r for r in load_jsonl(GOLD / f"x_claim_{split}_span.jsonl")}
    rows = load_jsonl(SPLITS / f"{split}.jsonl")
    langs = (lang,) if arm == "mono" else ARM_TRAIN_LANGS[arm]
    out = []
    for row in rows:
        if row["uid"] not in gold:
            continue
        if split == "train" and row["lang"] not in langs:
            continue
        g = gold[row["uid"]]
        out.append({"uid": row["uid"], "lang": row["lang"],
                    "tokens": g["tokens"], "tags": g["bio"]})
    return out


def encode(examples: list[dict], tokenizer, max_length: int):
    """Word-level BIO -> subword labels, first subword only."""
    encoded = tokenizer(
        [e["tokens"] for e in examples],
        is_split_into_words=True, truncation=True,
        max_length=max_length, padding=False,
    )
    labels = []
    for i, example in enumerate(examples):
        word_ids = encoded.word_ids(batch_index=i)
        previous, row = None, []
        for word_id in word_ids:
            if word_id is None:
                row.append(-100)                     # special token
            elif word_id != previous:
                row.append(LABEL_TO_ID[example["tags"][word_id]])
            else:
                row.append(-100)                     # continuation subword
            previous = word_id
        labels.append(row)
    encoded["labels"] = labels
    return encoded


def build_model(lora_r: int, lora_alpha: int):
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForTokenClassification

    model = AutoModelForTokenClassification.from_pretrained(
        BASE_MODEL, num_labels=len(SPAN_BIO),
        id2label=ID_TO_LABEL, label2id=LABEL_TO_ID,
    )
    peft_config = LoraConfig(
        task_type=TaskType.TOKEN_CLS, r=lora_r, lora_alpha=lora_alpha,
        lora_dropout=0.1, bias="none",
        # XLM-R's attention projections. The classification head is trained in
        # full regardless -- it is new, so there is nothing to adapt.
        target_modules=["query", "key", "value"],
        modules_to_save=["classifier"],
    )
    model = get_peft_model(model, peft_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  trainable {trainable:,} / {total:,} = {trainable / total:.2%}")
    return model, torch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/train_span.py")
    parser.add_argument("--arm", default="joint", choices=["joint", "mono", "zeroshot"])
    parser.add_argument("--lang", default=None, choices=["en", "hi", "pa"],
                        help="required for --arm mono")
    parser.add_argument("--epochs", type=float, default=5.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    args = parser.parse_args(argv)
    if args.arm == "mono" and not args.lang:
        parser.error("--arm mono needs --lang")
    set_all_seeds(SEED)

    name = f"span_xlmr_{args.arm}" + (f"_{args.lang}" if args.lang else "")
    out_dir = MODELS / name

    train = load_arm(args.arm, args.lang, "train")
    dev = load_arm(args.arm, args.lang, "dev")
    print(f"{name}: {len(train)} train, {len(dev)} dev "
          f"(dev is ALL languages, so a zero-shot arm is scored on what it never saw)")
    if not train:
        print("no training rows for this arm")
        return 2

    from transformers import (
        AutoTokenizer,
        DataCollatorForTokenClassification,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model, torch = build_model(args.lora_r, args.lora_alpha)

    class Dataset(torch.utils.data.Dataset):
        def __init__(self, examples):
            self.enc = encode(examples, tokenizer, args.max_length)

        def __len__(self):
            return len(self.enc["input_ids"])

        def __getitem__(self, i):
            return {k: v[i] for k, v in self.enc.items()}

    batch_size = args.batch_size
    started = time.time()
    while True:
        try:
            trainer = Trainer(
                model=model,
                args=TrainingArguments(
                    output_dir=str(out_dir / "_hf"),
                    num_train_epochs=args.epochs,
                    per_device_train_batch_size=batch_size,
                    per_device_eval_batch_size=batch_size,
                    learning_rate=args.lr,
                    fp16=torch.cuda.is_available(),
                    logging_steps=50,
                    save_strategy="no",
                    report_to=[],
                    seed=SEED,
                    dataloader_num_workers=0,
                ),
                train_dataset=Dataset(train),
                data_collator=DataCollatorForTokenClassification(tokenizer),
            )
            trainer.train()
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
    meta = {"arm": args.arm, "lang": args.lang, "base_model": BASE_MODEL,
            "seed": SEED, "epochs": args.epochs, "batch_size": batch_size,
            "lr": args.lr, "max_length": args.max_length,
            "lora_r": args.lora_r, "lora_alpha": args.lora_alpha,
            "n_train": len(train), "train_langs": list(
                (args.lang,) if args.arm == "mono" else ARM_TRAIN_LANGS[args.arm]),
            "peak_vram_gib": round(peak, 3),
            "minutes": round((time.time() - started) / 60, 1)}
    (out_dir / "training.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out_dir}")
    print(f"  peak VRAM {peak:.2f} GiB, {meta['minutes']} min, batch {batch_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
