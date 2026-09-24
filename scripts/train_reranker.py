"""Fine-tune XLM-R-base + LoRA as a claim-matching cross-encoder (FR-8).

    python scripts/mine_hard_negatives.py --split train
    python scripts/train_reranker.py

Writes a LoRA adapter to gitignored `data/interim/models/reranker_xlmr/`,
following the checkpoint policy in `docs/environment.md`.

## What it is for

The bi-encoder ranks well and scores badly: a correct top-1 averages cosine
0.7239 and a wrong one 0.6500, which gives no usable operating point for the
fast path (40.5% coverage at 62.7% precision; 1.7% coverage at 81.8%). A
bi-encoder compares two independently-built vectors. A cross-encoder reads the
post and the fact-check together, which is what lets it separate "same claim"
from "same topic" -- and "same topic, different claim" is what the bi-encoder's
wrong top-1 looks like.

## The comparison this has to win

`src/matching/rerankers.py` also has a **zero-shot** arm: mDeBERTa-XNLI, on disk
since Phase 1, trained on nothing of ours. Phase 3 ran the same pairing for
check-worthiness and the zero-shot arm won, so this is not a formality. A
trained model that cannot beat a model that has never seen the task has learned
the training set rather than the task.

## Leakage, stated rather than discovered

Training reads MultiClaim TRAIN and is evaluated on MultiClaim DEV, both frozen
and leakage-checked. The hard negatives are mined from the shared 78,077
fact-check pool, which contains fact-checks that are gold for dev queries -- that
is correct, because the pool has to hold the answers, and no dev LABEL is used.
But the training run does see some dev-answer TEXT in the negative class, and
that is worth knowing when reading the dev numbers.

## VRAM

~4.9 GiB usable, not NFR-3's 5.5 GB (`docs/environment.md`). A cross-encoder
packs two texts into one sequence, so it is heavier per row than Phase 3's
span tagger at the same batch size. `--batch-size` halves on OOM; the order
after that is gradient checkpointing, then 4-bit -- never a smaller model.
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

BASE_MODEL = "xlm-roberta-base"
MODELS = Path("data/interim/models")
PAIRS = Path("data/interim/reranker")
INTERIM = Path("data/interim/multiclaim")
META = Path("data/interim/index/factcheck_meta.jsonl")

ID_TO_LABEL = {0: "NotRelevant", 1: "Relevant"}
LABEL_TO_ID = {v: k for k, v in ID_TO_LABEL.items()}


def load_pairs(split: str, max_negatives_per_post: int | None) -> list[dict]:
    """Mined pairs, joined back to their text and optionally capped per post.

    The miner stores ids only -- writing the post beside each of its ~11
    candidates repeats it eleven times, and holding all of that at once thrashed
    a 16 GB machine into swap. The join happens here.

    The cap exists because the mined ratio is roughly 1 positive to 9 negatives
    and an unbalanced binary task will happily learn to answer "not relevant" to
    everything. Capping is preferred to class reweighting because the negatives
    arrive ordered by retriever score, so keeping the first few keeps the
    HARDEST ones -- reweighting would keep the easy tail at full strength.
    """
    path = PAIRS / f"{split}.jsonl"
    if not path.is_file():
        raise SystemExit(
            f"missing {path}. Run `python scripts/mine_hard_negatives.py "
            f"--split {split}` first."
        )
    posts = {r["uid"]: r["text"] for r in load_jsonl(INTERIM / f"{split}.jsonl")}
    candidates = {r["id"]: r["text"] for r in load_jsonl(META) if r.get("text")}

    kept, seen = [], collections.Counter()
    for row in load_jsonl(path):
        if row["label"] == 0 and max_negatives_per_post is not None:
            if seen[row["uid"]] >= max_negatives_per_post:
                continue
            seen[row["uid"]] += 1
        post = posts.get(row["uid"])
        candidate = candidates.get(row["fact_check_id"])
        if not post or not candidate:
            continue
        kept.append({"post": post, "candidate": candidate, "label": row["label"]})
    return kept


def build_model(lora_r: int, lora_alpha: int):
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForSequenceClassification

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=2, id2label=ID_TO_LABEL, label2id=LABEL_TO_ID,
    )
    peft_config = LoraConfig(
        task_type=TaskType.SEQ_CLS, r=lora_r, lora_alpha=lora_alpha,
        lora_dropout=0.1, bias="none",
        target_modules=["query", "key", "value"],
        modules_to_save=["classifier"],
    )
    model = get_peft_model(model, peft_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  trainable {trainable:,} / {total:,} = {trainable / total:.2%}")
    return model, torch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/train_reranker.py")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--max-negatives", type=int, default=4,
                        help="per post; the mined ratio is ~1:8 and the hardest "
                             "negatives come first")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    set_all_seeds(SEED)

    out_dir = MODELS / "reranker_xlmr"
    train = load_pairs("train", args.max_negatives)
    if args.limit:
        train = train[:args.limit]
    labels = collections.Counter(r["label"] for r in train)
    print(f"reranker_xlmr: {len(train)} pairs "
          f"({labels[1]} relevant, {labels[0]} not)")
    if not train:
        print("no training pairs")
        return 2

    from transformers import AutoTokenizer, Trainer, TrainingArguments

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model, torch = build_model(args.lora_r, args.lora_alpha)

    class Dataset(torch.utils.data.Dataset):
        """Tokenized lazily per item.

        Encoding all pairs up front would hold ~1 GB of padded tensors before
        training starts; the collator pads per batch instead.
        """

        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            row = self.rows[i]
            enc = tokenizer(row["post"], row["candidate"], truncation=True,
                            max_length=args.max_length)
            enc["labels"] = int(row["label"])
            return enc

    from transformers import DataCollatorWithPadding

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
                    logging_steps=100,
                    save_strategy="no",
                    report_to=[],
                    seed=SEED,
                    dataloader_num_workers=0,
                ),
                train_dataset=Dataset(train),
                data_collator=DataCollatorWithPadding(tokenizer),
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
    meta = {"base_model": BASE_MODEL, "seed": SEED, "epochs": args.epochs,
            "batch_size": batch_size, "lr": args.lr,
            "max_length": args.max_length, "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha, "n_train": len(train),
            "label_counts": {"Relevant": labels[1], "NotRelevant": labels[0]},
            "max_negatives_per_post": args.max_negatives,
            "peak_vram_gib": round(peak, 3),
            "minutes": round((time.time() - started) / 60, 1)}
    (out_dir / "training.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out_dir}")
    print(f"  peak VRAM {peak:.2f} GiB, {meta['minutes']} min, batch {batch_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
