"""Train the in-domain Word2Vec rung of the embedding ladder (Phase 2).

    python scripts/train_word2vec.py

Writes data/interim/models/word2vec.kv (gitignored).

## Why in-domain rather than pretrained

There is no credible pretrained Punjabi Word2Vec, and the fastText vector files
are ~7 GB per language. Training here takes minutes and a few MB. It is also the
more honest version of this rung: the question the ladder asks is what a static
embedding can do on THIS data, and a model trained on this data answers it
directly. It handles romanized text for free, because it is trained on romanized
text rather than on a corpus that has never seen any.

## Corpus

Fact-check text (the retrieval index itself) plus TRAIN posts. Dev and test post
text is deliberately excluded. Fitting an unsupervised model on the corpus you
are going to search is normal and not leakage -- the corpus is the haystack, not
the answer key -- but fitting it on the queries you will be scored on is a
different thing, and not worth the argument for what it would buy.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from data.multiclaim import load_fact_checks, load_pairs  # noqa: E402
from retrieval.encoders import WORD2VEC_PATH  # noqa: E402

INTERIM = Path("data/interim")

# Keep script-bearing runs and drop punctuation. Devanagari, Gurmukhi and Latin
# in one pattern, because the corpus mixes all three inside single documents.
_TOKEN = re.compile(r"[A-Za-zऀ-ॿ਀-੿]+|\d+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def corpus() -> list[list[str]]:
    sentences: list[list[str]] = []

    wanted = {fc_id for _, fc_id, _ in load_pairs()}
    for fc in load_fact_checks(ids=wanted).values():
        tokens = tokenize(" ".join(p for p in (fc.claim, fc.title) if p))
        if len(tokens) >= 3:
            sentences.append(tokens)
    print(f"  {len(sentences)} fact-check documents")

    before = len(sentences)
    train_texts = INTERIM / "multiclaim" / "train.jsonl"
    if train_texts.is_file():
        for row in load_jsonl(train_texts):
            tokens = tokenize(row["text"])
            if len(tokens) >= 3:
                sentences.append(tokens)
    print(f"  {len(sentences) - before} train posts (dev/test excluded on purpose)")
    return sentences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/train_word2vec.py")
    parser.add_argument("--dim", type=int, default=300)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--min-count", type=int, default=3)
    args = parser.parse_args(argv)
    set_all_seeds(SEED)

    print("building the corpus")
    sentences = corpus()
    total = sum(len(s) for s in sentences)
    print(f"  {len(sentences)} documents, {total} tokens")

    from gensim.models import Word2Vec

    print(f"training skip-gram, dim={args.dim}, {args.epochs} epochs")
    model = Word2Vec(
        sentences=sentences,
        vector_size=args.dim,
        window=5,
        min_count=args.min_count,
        sg=1,                 # skip-gram: better on rare words, and Punjabi is all rare words
        negative=10,
        epochs=args.epochs,
        seed=SEED,
        workers=1,            # reproducibility: >1 worker makes training order nondeterministic
    )
    WORD2VEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.wv.save(str(WORD2VEC_PATH))
    print(f"wrote {WORD2VEC_PATH}  vocab={len(model.wv)}  dim={model.wv.vector_size}")

    for probe in ("vaccine", "sarkar", "modi", "सरकार"):
        if probe in model.wv:
            neighbours = ", ".join(w for w, _ in model.wv.most_similar(probe, topn=5))
            print(f"  {probe:10s} -> {neighbours}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
