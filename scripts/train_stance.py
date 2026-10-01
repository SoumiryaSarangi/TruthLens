"""Fine-tune XLM-R-base + LoRA for stance, with or without the evidence (FR-10).

    python scripts/train_stance.py                  # reads claim + evidence
    python scripts/train_stance.py --claim-only     # the shortcut control

Trains on the averitec_stance TRAIN split only, whose membership is inherited
from the frozen AVeriTeC splits, so no dev or test claim reaches training. Writes
a LoRA adapter to gitignored `data/interim/models/stance_xlmr[_claimonly]/`.

## Why there are two runs

Every answer of a claim carries that claim's verdict, so a model can score well
by predicting from the claim alone. Measured on TF-IDF, reading the evidence
bought nothing over the claim (-0.0036 macro-F1 on answered dev rows). The
claim-only run is trained identically on the claim alone; the gap between the
two -- on ANSWERED rows, where the Unanswerable string cannot decide it -- is
what says whether the full model reads evidence.

## Input and labels

Pair input is (evidence, claim), premise then hypothesis, matching `stance.nli`.
Labels are `STANCES` in `stance.xlmr`, so training and inference cannot disagree
about which logit means what. No class weighting in the loss: the evaluation is
macro-F1 and Refutes is ~60% of train, but weighting would change what the
claim-only control measures -- both runs are trained identically instead, and the
comparison is between them.

VRAM: ~4.9 GiB usable. Halves the batch on OOM; after that, gradient
checkpointing, then 4-bit -- never a smaller model.
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
from data.loaders import stance_parent_source_id  # noqa: E402
from stance.folds import N_FOLDS, fold_of  # noqa: E402
from stance.xlmr import MODELS, STANCES  # noqa: E402

BASE_MODEL = "xlm-roberta-base"
SPLIT = Path("data/splits/averitec_stance/train.jsonl")
INTERIM = Path("data/interim/averitec_stance/train.jsonl")
LABEL_TO_ID = {s: i for i, s in enumerate(STANCES)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/train_stance.py")
    ap.add_argument("--claim-only", action="store_true")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    # Phase 6 cross-fitting (decision D2): train on every claim OUTSIDE this
    # fold, so the claims inside it can be scored by a model that never saw them.
    ap.add_argument("--fold", type=int, default=None)
    ap.add_argument("--n-folds", type=int, default=N_FOLDS)
    args = ap.parse_args(argv)
    set_all_seeds(SEED)

    name = "stance_xlmr_claimonly" if args.claim_only else "stance_xlmr"
    if args.fold is not None:
        name += f"_fold{args.fold}"
    out_dir = MODELS / name
    split = list(load_jsonl(SPLIT))
    labels = {r["uid"]: r["label"] for r in split}
    if args.fold is not None:
        held_out = {r["uid"] for r in split
                    if fold_of(stance_parent_source_id(r["source_id"]),
                               args.n_folds) == args.fold}
        labels = {u: lab for u, lab in labels.items() if u not in held_out}
    rows = [r for r in load_jsonl(INTERIM) if r["uid"] in labels]
    counts = collections.Counter(labels[r["uid"]] for r in rows)
    print(f"{name}: {len(rows)} pairs over {len({r['claim'] for r in rows})} claims "
          f"{dict(counts)}")

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
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(STANCES),
        id2label=dict(enumerate(STANCES)), label2id=LABEL_TO_ID)
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.SEQ_CLS, r=args.lora_r, lora_alpha=args.lora_alpha,
        lora_dropout=0.1, bias="none", target_modules=["query", "key", "value"],
        modules_to_save=["classifier"]))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  trainable {trainable:,}")

    class Dataset(torch.utils.data.Dataset):
        def __len__(self):
            return len(rows)

        def __getitem__(self, i):
            row = rows[i]
            if args.claim_only:
                enc = tokenizer(row["claim"], truncation=True, max_length=args.max_length)
            else:
                enc = tokenizer(row["evidence"], row["claim"], truncation=True,
                                max_length=args.max_length)
            enc["labels"] = LABEL_TO_ID[labels[row["uid"]]]
            return enc

    batch_size = args.batch_size
    started = time.time()
    while True:
        try:
            Trainer(
                model=model,
                args=TrainingArguments(
                    output_dir=str(out_dir / "_hf"), num_train_epochs=args.epochs,
                    per_device_train_batch_size=batch_size, learning_rate=args.lr,
                    fp16=torch.cuda.is_available(), logging_steps=50,
                    save_strategy="no", report_to=[], seed=SEED,
                    dataloader_num_workers=0),
                train_dataset=Dataset(),
                data_collator=DataCollatorWithPadding(tokenizer),
            ).train()
            break
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if batch_size <= 1:
                print("OOM at batch size 1. Next: gradient checkpointing, then 4-bit.")
                return 1
            batch_size //= 2
            print(f"  OOM -> halving batch size to {batch_size}")

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    peak = torch.cuda.max_memory_allocated() / 2**30 if torch.cuda.is_available() else 0.0
    (out_dir / "training.json").write_text(json.dumps({
        "claim_only": args.claim_only, "base_model": BASE_MODEL, "seed": SEED,
        "fold": args.fold, "n_folds": args.n_folds if args.fold is not None else None,
        "epochs": args.epochs, "batch_size": batch_size, "lr": args.lr,
        "max_length": args.max_length, "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha, "n_train": len(rows),
        "label_counts": dict(counts), "peak_vram_gib": round(peak, 3),
        "minutes": round((time.time() - started) / 60, 1)}, indent=2), encoding="utf-8")
    print(f"wrote {out_dir}  peak VRAM {peak:.2f} GiB, "
          f"{(time.time() - started) / 60:.1f} min, batch {batch_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
