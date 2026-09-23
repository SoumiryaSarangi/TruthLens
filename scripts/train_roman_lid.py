"""Train the romanized language-ID classifier (FR-3).

    python scripts/train_roman_lid.py

Reads TRAIN SPLITS ONLY and writes data/interim/models/roman_lid.joblib.

The `dev` splits -- including all 100 hand-typed forwards -- are never opened
here. That is the whole point: if they were, the FR-3 number measured on them
would be a training accuracy wearing an evaluation's clothes.

Punjabi is the constraint. All of train holds 42 genuinely romanized Punjabi
rows, so most of the Punjabi signal is SYNTHESISED by romanizing native-script
rows. Synthetic romanization is internally consistent and real typing is not,
so the model sees a tidier Punjabi than it is later asked about. Reported, not
hidden: the held-out figures printed at the end are split by real vs synthetic
so the difference is visible rather than averaged away.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl  # noqa: E402
from common.seeds import SEED, set_all_seeds  # noqa: E402
from preprocess.roman_lid import LABELS, MODEL_PATH, build_pipeline  # noqa: E402
from preprocess.translit import RuleBasedTransliterator  # noqa: E402

SPLITS = Path("data/splits")
INTERIM = Path("data/interim")

NATIVE_SCRIPT = {"hi": "deva", "pa": "guru"}

DAKSHINA = Path("data/raw/dakshina/extracted")

# Dakshina ships its romanized sentences as dev + test and nothing else, so the
# two have to be divided by hand. TEST trains this classifier; DEV is reserved
# for evaluating transliteration (FR-5). No Dakshina row is ever both trained on
# and evaluated on, for any task.
DAKSHINA_TRAIN_SPLIT = "test"

# English dwarfs everything else. Capping it keeps the model from learning that
# `en` is the safe answer, which is the exact failure fastText already has.
MAX_PER_CLASS = 6000


def load_train_rows() -> list[tuple[str, str, str, bool]]:
    """(text, lang, script, is_synthetic) from every train split on disk."""
    translit = RuleBasedTransliterator()
    out: list[tuple[str, str, str, bool]] = []

    for dataset_dir in sorted(SPLITS.iterdir()):
        split_file = dataset_dir / "train.jsonl"
        text_file = INTERIM / dataset_dir.name / "train.jsonl"
        if not split_file.is_file() or not text_file.is_file():
            continue
        texts = {r["uid"]: r["text"] for r in load_jsonl(text_file)}
        for row in load_jsonl(split_file):
            text = texts.get(row["uid"], "").strip()
            if len(text) < 20:          # too short to carry n-gram evidence
                continue
            lang, script = row["lang"], row["script"]
            if lang not in LABELS:
                continue
            if script == "latn":
                out.append((text, lang, script, False))
            elif script == NATIVE_SCRIPT.get(lang):
                # Synthesise the romanized form the model will actually see.
                romanized = translit.to_roman(text, lang)
                if romanized and romanized != text:
                    out.append((romanized, lang, script, True))
    return out


def load_dakshina_rows() -> list[tuple[str, str, str, bool]]:
    """Elicited romanized sentences, which is where Punjabi actually comes from.

    All of train across every other dataset holds 42 romanized Punjabi rows.
    Dakshina holds about 5,000. It is cleaner than a WhatsApp forward -- it is
    Wikipedia text that annotators were asked to romanize, so the spelling is
    more consistent than real typing -- but the alternative is not having
    Punjabi at all.
    """
    out: list[tuple[str, str, str, bool]] = []
    for lang in ("hi", "pa"):
        path = DAKSHINA / lang / f"{lang}.romanized.rejoined.{DAKSHINA_TRAIN_SPLIT}.roman.txt"
        if not path.is_file():
            print(f"  (no Dakshina for {lang}; run scripts/download_models.py)")
            continue
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
        kept = [ln for ln in lines if len(ln) >= 20]
        out.extend((ln, lang, "latn", False) for ln in kept)
        print(f"  dakshina {lang}: {len(kept)} romanized sentences")
    return out


def balance(rows, seed: int = SEED):
    """Cap each language, keeping every REAL romanized row first.

    Real rows are scarce and synthetic rows are plentiful, so a uniform sample
    would drown the 42 real Punjabi examples in synthetic ones.
    """
    rng = random.Random(seed)
    by_lang: dict[str, list] = {lang: [] for lang in LABELS}
    for row in rows:
        by_lang[row[1]].append(row)

    kept = []
    for lang, items in by_lang.items():
        real = [r for r in items if not r[3]]
        synthetic = [r for r in items if r[3]]
        rng.shuffle(real)
        rng.shuffle(synthetic)
        take_real = real[:MAX_PER_CLASS]
        take_synth = synthetic[:max(0, MAX_PER_CLASS - len(take_real))]
        kept.extend(take_real + take_synth)
        print(f"  {lang}: {len(take_real)} real + {len(take_synth)} synthetic "
              f"(available {len(real)} / {len(synthetic)})")
    rng.shuffle(kept)
    return kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/train_roman_lid.py")
    parser.add_argument("--holdout", type=float, default=0.15,
                        help="fraction of TRAIN held back to report on")
    args = parser.parse_args(argv)
    set_all_seeds(SEED)

    print("loading train splits (project dev and test are never opened here)")
    rows = load_train_rows()
    print(f"  {len(rows)} candidate rows from project splits")
    print("loading Dakshina romanized sentences:")
    rows += load_dakshina_rows()
    print(f"  {len(rows)} candidate rows total")
    print("balancing:")
    rows = balance(rows)
    print(f"  {len(rows)} after balancing")

    cut = int(len(rows) * (1 - args.holdout))
    train, held = rows[:cut], rows[cut:]
    print(f"\ntraining on {len(train)}, holding back {len(held)} from TRAIN")

    model = build_pipeline(SEED)
    model.fit([r[0] for r in train], [r[1] for r in train])

    from sklearn.metrics import classification_report

    predicted = model.predict([r[0] for r in held])
    truth = [r[1] for r in held]
    print("\nheld-out-from-TRAIN report (NOT the FR-3 number -- that is measured")
    print("on dev through `make eval`, which is the only place a metric counts):")
    print(classification_report(truth, predicted, digits=4, zero_division=0))

    # The split that actually matters, because synthetic romanization is tidier
    # than real typing and averaging the two hides it.
    for kind, is_syn in (("real romanized", False), ("synthetic romanized", True)):
        idx = [i for i, r in enumerate(held) if r[3] is is_syn]
        if not idx:
            continue
        correct = sum(1 for i in idx if predicted[i] == truth[i])
        counts = Counter(truth[i] for i in idx)
        print(f"  {kind:22s} {correct}/{len(idx)} = {correct / len(idx):.4f}   {dict(counts)}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(model, MODEL_PATH, compress=3)
    size = MODEL_PATH.stat().st_size / 1e6
    print(f"\nwrote {MODEL_PATH}  ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
