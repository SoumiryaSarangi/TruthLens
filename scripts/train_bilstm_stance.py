"""Train the siamese BiLSTM stance baseline (FR-10, Unit III).

    python scripts/train_bilstm_stance.py

Trains on the averitec_stance TRAIN split only (membership inherited from the
frozen AVeriTeC splits). Writes gitignored `data/interim/models/stance_bilstm/`:
`model.pt`, `vocab.json`, `config.json`, `training.json`.

Embeddings are XLM-R's input rows, frozen, restricted to tokens seen in training
(the full matrix is 768 MB; the kept rows are a few tens of MB). The recurrent
part and the head are trained from scratch. Same labels and order as
`stance.bilstm.STANCES`, so training and inference cannot disagree about which
logit means what. No class weighting, like the XLM-R arm, so the two are
comparable.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from stance.bilstm import MAX_TOKENS, MODELS, PAD, STANCES, UNK, Vocab, build_net  # noqa: E402

TOKENIZER = "xlm-roberta-base"
SPLIT = Path("data/splits/averitec_stance/train.jsonl")
INTERIM = Path("data/interim/averitec_stance/train.jsonl")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/train_bilstm_stance.py")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=256)
    args = ap.parse_args(argv)
    set_all_seeds(SEED)

    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer

    out_dir = MODELS / "stance_bilstm"
    labels = {r["uid"]: r["label"] for r in load_jsonl(SPLIT)}
    rows = [r for r in load_jsonl(INTERIM) if r["uid"] in labels]
    y = [STANCES.index(labels[r["uid"]]) for r in rows]
    print(f"stance_bilstm: {len(rows)} pairs "
          f"{dict(collections.Counter(labels[r['uid']] for r in rows))}")

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)
    texts = [r["claim"] for r in rows] + [r["evidence"] for r in rows]
    seen = sorted({t for ids in tokenizer(texts, truncation=True, max_length=MAX_TOKENS,
                                          add_special_tokens=False)["input_ids"]
                   for t in ids})
    rows_of = {tok: i + 2 for i, tok in enumerate(seen)}          # 0 pad, 1 unknown
    full = AutoModel.from_pretrained(TOKENIZER).get_input_embeddings().weight
    full = full.detach().float().numpy()
    embeddings = np.zeros((len(seen) + 2, full.shape[1]), dtype=np.float32)
    embeddings[UNK] = full.mean(axis=0)
    embeddings[2:] = full[seen]
    del full
    print(f"  vocab: {len(seen)} XLM-R tokens seen in training "
          f"({embeddings.nbytes / 2**20:.0f} MB of embeddings kept)")

    vocab = Vocab(rows_of)
    claims = vocab.encode(tokenizer, [r["claim"] for r in rows])
    evidence = vocab.encode(tokenizer, [r["evidence"] for r in rows])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = build_net(embeddings, hidden=args.hidden).to(device)
    optimiser = torch.optim.Adam([p for p in net.parameters() if p.requires_grad],
                                 lr=args.lr)
    loss_fn = torch.nn.CrossEntropyLoss()

    order = list(range(len(rows)))
    rng = random.Random(SEED)
    started = time.time()
    for epoch in range(args.epochs):
        net.train()
        rng.shuffle(order)
        total = 0.0
        for start in range(0, len(order), args.batch_size):
            idx = order[start:start + args.batch_size]
            c = torch.tensor(_pad([claims[i] for i in idx]), device=device)
            e = torch.tensor(_pad([evidence[i] for i in idx]), device=device)
            target = torch.tensor([y[i] for i in idx], device=device)
            optimiser.zero_grad()
            loss = loss_fn(net(c, e), target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
            optimiser.step()
            total += loss.item() * len(idx)
        print(f"  epoch {epoch + 1}/{args.epochs}  loss {total / len(order):.4f}",
              flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), out_dir / "model.pt")
    (out_dir / "vocab.json").write_text(json.dumps(rows_of), encoding="utf-8")
    (out_dir / "config.json").write_text(json.dumps({
        "tokenizer": TOKENIZER, "n_rows": int(embeddings.shape[0]),
        "dim": int(embeddings.shape[1]), "hidden": args.hidden}), encoding="utf-8")
    (out_dir / "training.json").write_text(json.dumps({
        "seed": SEED, "epochs": args.epochs, "batch_size": args.batch_size,
        "lr": args.lr, "hidden": args.hidden, "n_train": len(rows),
        "vocab_rows": int(embeddings.shape[0]),
        "minutes": round((time.time() - started) / 60, 1)}, indent=2), encoding="utf-8")
    print(f"wrote {out_dir} in {(time.time() - started) / 60:.1f} min")
    return 0


def _pad(batch: list[list[int]]) -> list[list[int]]:
    """Trim each batch to its own longest row, so short batches stay short."""
    width = max(1, max((sum(1 for t in row if t != PAD) for row in batch), default=1))
    return [row[:width] + [PAD] * max(0, width - len(row)) for row in batch]


if __name__ == "__main__":
    raise SystemExit(main())
