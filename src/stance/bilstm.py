"""Siamese BiLSTM stance classifier with attention pooling (FR-10, Unit III).

The PRD's stance BASELINE (`PRD.md:77`: "BiLSTM baseline, XLM-R-base model"),
and the syllabus's recurrent-network unit. Trained by
`scripts/train_bilstm_stance.py`.

## Architecture

Claim and evidence are each encoded by one shared BiLSTM, pooled by learned
attention, and compared InferSent-style:

    u = attend(BiLSTM(claim))      v = attend(BiLSTM(evidence))
    features = [u ; v ; |u - v| ; u * v]   ->   MLP   ->   3 stances

The comparison features are what let a sentence encoder model a RELATION between
two texts rather than two independent topics -- which is the only route by which
a model trained on these labels can use evidence at all (see `stance/xlmr.py`).

## Embeddings

XLM-R's tokenizer and its input embedding rows, frozen. Multilingual subwords
from day one, and no in-domain word vectors to train. Only the rows for tokens
that occur in training are kept -- the full matrix is 250,002 x 768 fp32,
768 MB, for a model whose recurrent part is a few MB. A token never seen in
training maps to a shared unknown row.

## Attention is the Unit IV fallback

Cut list item 4 replaces the seq2seq summariser with "attention visualisation on
the stance model". `attend()` returns the per-token weights for exactly that
figure.

torch is imported lazily: `tests/test_contracts.py` forbids it at module scope,
so the network class is built by a factory.
"""

from __future__ import annotations

import json
from pathlib import Path

from stance.nli import StanceResult

MODELS = Path("data/interim/models")
STANCES = ("Supports", "Refutes", "Neutral")
MAX_TOKENS = 128
PAD, UNK = 0, 1


def build_net(embeddings, hidden: int = 256, dropout: float = 0.3):
    """The network, built lazily so importing this module needs no torch."""
    import torch
    from torch import nn

    class SiameseBiLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding.from_pretrained(
                torch.as_tensor(embeddings, dtype=torch.float32),
                freeze=True, padding_idx=PAD)
            self.lstm = nn.LSTM(self.embed.embedding_dim, hidden, batch_first=True,
                                bidirectional=True)
            self.attn = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.Tanh(),
                                      nn.Linear(hidden, 1, bias=False))
            self.head = nn.Sequential(nn.Dropout(dropout),
                                      nn.Linear(8 * hidden, hidden), nn.ReLU(),
                                      nn.Dropout(dropout),
                                      nn.Linear(hidden, len(STANCES)))

        def encode(self, ids):
            mask = ids != PAD
            states, _ = self.lstm(self.embed(ids))
            scores = self.attn(states).squeeze(-1).masked_fill(~mask, -1e9)
            weights = torch.softmax(scores, dim=-1)
            return (weights.unsqueeze(-1) * states).sum(1), weights

        def forward(self, claim_ids, evidence_ids):
            u, _ = self.encode(claim_ids)
            v, _ = self.encode(evidence_ids)
            return self.head(torch.cat([u, v, (u - v).abs(), u * v], dim=-1))

    return SiameseBiLSTM()


class Vocab:
    """XLM-R token id -> a compact row index, for tokens seen in training."""

    def __init__(self, rows: dict[int, int]):
        self.rows = rows

    def encode(self, tokenizer, texts: list[str], max_tokens: int = MAX_TOKENS):
        ids = tokenizer(texts, truncation=True, max_length=max_tokens,
                        add_special_tokens=False)["input_ids"]
        width = max(1, max((len(x) for x in ids), default=1))
        return [[self.rows.get(t, UNK) for t in x] + [PAD] * (width - len(x))
                for x in ids]


class StanceModelMissing(RuntimeError):
    """The BiLSTM has not been trained yet."""


class BiLSTMStance:
    name = "stance"
    impl = "bilstm"

    def __init__(self, model_dir: str | Path | None = None, batch_size: int = 64,
                 device: str | None = None, **_: object) -> None:
        self.model_dir = Path(model_dir) if model_dir else MODELS / "stance_bilstm"
        self.batch_size = batch_size
        self._device = device
        self._net = self._tokenizer = self._vocab = None

    def _load(self):
        if self._net is None:
            weights = self.model_dir / "model.pt"
            if not weights.is_file():
                raise StanceModelMissing(
                    f"no model at {weights}. Run "
                    "`python scripts/train_bilstm_stance.py`.")
            import numpy as np
            import torch
            from transformers import AutoTokenizer

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            config = json.loads((self.model_dir / "config.json").read_text("utf-8"))
            vocab = json.loads((self.model_dir / "vocab.json").read_text("utf-8"))
            self._vocab = Vocab({int(k): v for k, v in vocab.items()})
            self._tokenizer = AutoTokenizer.from_pretrained(config["tokenizer"])
            embeddings = np.zeros((config["n_rows"], config["dim"]), dtype=np.float32)
            net = build_net(embeddings, hidden=config["hidden"])
            net.load_state_dict(torch.load(weights, map_location="cpu"))
            self._net = net.to(self._device).eval()
        return self._net

    def _tensors(self, claims, passages):
        import torch
        c = self._vocab.encode(self._tokenizer, claims)
        e = self._vocab.encode(self._tokenizer, passages)
        return (torch.tensor(c, device=self._device), torch.tensor(e, device=self._device))

    def label(self, claim: str, passages: list[str]) -> list[StanceResult]:
        if not passages:
            return []
        # Loaded first, so a missing model refuses whether or not torch is here.
        net = self._load()
        import torch

        out: list[StanceResult] = []
        for start in range(0, len(passages), self.batch_size):
            batch = passages[start:start + self.batch_size]
            claim_ids, evidence_ids = self._tensors([claim] * len(batch), batch)
            with torch.inference_mode():
                probs = torch.softmax(net(claim_ids, evidence_ids), dim=-1).tolist()
            for row in probs:
                dist = dict(zip(STANCES, row, strict=True))
                best = max(dist, key=dist.get)
                out.append(StanceResult(best, dist[best], dist))
        return out

    def attend(self, text: str) -> list[tuple[str, float]]:
        """(token, attention weight) over one text -- the Unit IV figure."""
        # Loaded first, so a missing model refuses whether or not torch is here.
        net = self._load()
        import torch

        ids, _ = self._tensors([text], [text])
        with torch.inference_mode():
            _, weights = net.encode(ids)
        tokens = self._tokenizer.tokenize(text)[:MAX_TOKENS]
        return list(zip(tokens, weights[0, :len(tokens)].tolist(), strict=True))
