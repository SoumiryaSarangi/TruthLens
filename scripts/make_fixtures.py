"""Generate the toy fixtures the harness tests run against.

Unlike data/splits/, these fixtures ARE regenerable -- they contain invented
text, not dataset content. Rerun with `python scripts/make_fixtures.py` and
commit the result.

Two fixture datasets:

  toy_clean/  no leakage. The acceptance-test target for `make eval`.
  toy_leaky/  three planted leaks, one of each kind the detector must catch:
              a shared uid, an identical claim re-keyed, and a paraphrase.
              tests/test_leakage_detector.py asserts these are found. A
              leakage test that has never failed is not evidence of anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import sha1_text  # noqa: E402
from common.io_jsonl import write_json, write_jsonl  # noqa: E402
from data.normalize import normalize_for_hashing  # noqa: E402
from data.simhash import simhash_hex  # noqa: E402
from data.splits import build_lock  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

# (lang, script, label, text)
CLEAN: dict[str, list[tuple[str, str, str, str]]] = {
    "train": [
        ("en", "latn", "Refuted", "Drinking hot water every hour cures the common cold in two days."),
        ("en", "latn", "Supported", "India's general election in 2024 was held in seven phases."),
        ("en", "latn", "NEI", "A new bridge will open in Guwahati before the monsoon next year."),
        ("en", "latn", "NotAClaim", "Good morning everyone, please forward this to ten friends."),
        ("en", "latn", "Refuted", "The government is giving free laptops to every college student."),
        ("en", "latn", "Supported", "The Reserve Bank of India kept the repo rate unchanged in June."),
        ("hi", "deva", "Refuted", "सरकार सभी किसानों को मुफ्त बिजली दे रही है।"),
        ("hi", "deva", "Supported", "भारत ने चंद्रयान-3 को सफलतापूर्वक लॉन्च किया था।"),
        ("hi", "deva", "NEI", "अगले महीने पेट्रोल की कीमत बढ़ सकती है।"),
        ("hi", "latn", "Refuted", "Sarkar sabhi kisanon ko muft bijli de rahi hai bhai."),
        ("hi", "latn", "NotAClaim", "Bhai ye message sabko forward karo jaldi se."),
        ("pa", "guru", "Refuted", "ਸਰਕਾਰ ਸਾਰੇ ਕਿਸਾਨਾਂ ਨੂੰ ਮੁਫਤ ਬਿਜਲੀ ਦੇ ਰਹੀ ਹੈ।"),
        ("pa", "guru", "Supported", "ਪੰਜਾਬ ਵਿੱਚ ਕਣਕ ਦੀ ਵਾਢੀ ਅਪ੍ਰੈਲ ਵਿੱਚ ਸ਼ੁਰੂ ਹੁੰਦੀ ਹੈ।"),
        ("pa", "latn", "NEI", "Agle saal Punjab vich navi metro line shuru ho sakdi hai."),
    ],
    "dev": [
        ("en", "latn", "Supported", "The Indian Space Research Organisation is headquartered in Bengaluru."),
        ("en", "latn", "Refuted", "Eating raw garlic prevents every known viral infection."),
        ("en", "latn", "NEI", "A cricket stadium may be built in Srinagar within three years."),
        ("en", "latn", "NotAClaim", "Please share this with all your WhatsApp groups today."),
        ("hi", "deva", "Refuted", "नींबू पानी पीने से कैंसर ठीक हो जाता है।"),
        ("hi", "deva", "Supported", "दिल्ली मेट्रो की पहली लाइन 2002 में खुली थी।"),
        ("hi", "latn", "Refuted", "Neembu paani peene se cancer theek ho jata hai pakka."),
        ("pa", "guru", "Refuted", "ਹਲਦੀ ਵਾਲਾ ਦੁੱਧ ਪੀਣ ਨਾਲ ਸਾਰੀਆਂ ਬਿਮਾਰੀਆਂ ਠੀਕ ਹੁੰਦੀਆਂ ਹਨ।"),
        ("pa", "latn", "NEI", "Amritsar vich navan airport terminal agle saal khul sakda hai."),
    ],
    "test": [
        ("en", "latn", "Refuted", "Mobile towers emit radiation that ripens mangoes overnight."),
        ("en", "latn", "Supported", "The Ganges flows through both India and Bangladesh."),
        ("hi", "deva", "NEI", "सरकार नई शिक्षा नीति पर विचार कर रही है।"),
        ("hi", "latn", "Refuted", "Mobile tower ki radiation se aam raat bhar mein pak jate hain."),
        ("pa", "guru", "Supported", "ਗੁਰੂ ਨਾਨਕ ਦੇਵ ਜੀ ਦਾ ਜਨਮ 1469 ਵਿੱਚ ਹੋਇਆ।"),
    ],
}


def make_record(dataset: str, split: str, idx: int, lang: str, script: str,
                label: str, text: str, *, source_id: str | None = None) -> dict:
    normalised = normalize_for_hashing(text)
    return {
        "uid": f"{dataset}:{lang}:{split}:{idx:04d}",
        "dataset": dataset,
        "split": split,
        "lang": lang,
        "script": script,
        "source_id": source_id or f"src-{dataset}-{split}-{idx:04d}",
        "label": label,
        "label_set": "verdict_5class",
        "text_sha1": sha1_text(normalised),
        "simhash64": simhash_hex(text),
        "n_chars": len(text),
    }


TEXTS: dict[str, dict[str, str]] = {}


def build(dataset: str, spec: dict[str, list[tuple[str, str, str, str]]]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    store = TEXTS.setdefault(dataset, {})
    for split, rows in spec.items():
        built = []
        for i, (lang, script, label, text) in enumerate(rows):
            rec = make_record(dataset, split, i, lang, script, label, text)
            store[rec["uid"]] = text
            built.append(rec)
        out[split] = built
    return out


def plant_leaks(splits: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Insert one of each leak kind, so the detector has something to find."""
    train, dev = splits["train"], splits["dev"]

    # LEAK 1 -- the same uid in two splits.
    shared = dict(train[0])
    shared["split"] = "dev"
    dev.append(shared)

    # LEAK 2 -- the same claim re-keyed under a new uid and source_id.
    requeued = dict(train[6])
    requeued["uid"] = "toy_leaky:hi:dev:9001"
    requeued["split"] = "dev"
    requeued["source_id"] = "src-different-entirely"
    dev.append(requeued)

    # LEAK 3 -- forward header and a flag emoji bolted on. The normaliser
    # strips both, so this surfaces as an EXACT duplicate, which is the point:
    # the cheap check catches the most common real-world case.
    original_text = CLEAN["train"][1][3]
    forwarded = f"Forwarded many times: {original_text} \U0001f1ee\U0001f1f3"
    near = make_record("toy_leaky", "dev", 9002, "en", "latn", "Supported", forwarded)
    near["source_id"] = "src-forwarded"
    TEXTS["toy_leaky"][near["uid"]] = forwarded
    dev.append(near)

    # LEAK 4 -- punctuation-only variant. Survives normalisation, so it has to
    # be caught by SimHash proximity rather than by the exact hash. This is the
    # case that proves the near-duplicate path actually works.
    punct = CLEAN["train"][5][3].replace(".", "!!")
    near2 = make_record("toy_leaky", "dev", 9003, "en", "latn", "Supported", punct)
    near2["source_id"] = "src-punctuation"
    TEXTS["toy_leaky"][near2["uid"]] = punct
    dev.append(near2)

    return splits


def emit(name: str, splits: dict[str, list[dict]], texts: dict[str, str]) -> None:
    """Write one fixture dataset. The lock covering it is written once, at the end.

    `texts.jsonl` carries the source text alongside the manifest. Real splits
    never do this -- it would redistribute licensed data -- but fixture text is
    invented, and without it the near-duplicate check cannot be CONFIRMED and
    only warns. tests/test_leakage_detector.py needs a hard failure to assert.
    """
    target = FIXTURES / name
    for split, rows in splits.items():
        write_jsonl(target / f"{split}.jsonl", rows)
    write_jsonl(target / "texts.jsonl",
                [{"uid": uid, "text": text} for uid, text in sorted(texts.items())])
    counts = ", ".join(f"{s}={len(r)}" for s, r in sorted(splits.items()))
    print(f"  {name:<12} {counts}")


def emit_lock() -> None:
    """One SPLITS.lock over all fixture datasets.

    Mirrors the real layout exactly: data/splits/SPLITS.lock sits above the
    per-dataset directories and its keys look like "averitec/dev.jsonl". The
    fixtures must exercise the same code path, or the freeze check is tested
    in a shape it never meets in production.
    """
    entries = build_lock(FIXTURES)
    write_json(FIXTURES / "SPLITS.lock", {"version": 1, "files": entries})
    print(f"  {'SPLITS.lock':<12} {len(entries)} files locked")


def emit_demo_predictions(splits: dict[str, list[dict]]) -> None:
    """A stand-in 'model' output, so `make eval` has something to score.

    Deliberately imperfect and deterministic: every third row is wrong. It
    exists to prove the harness end to end, and its numbers mean nothing.
    """
    dev = splits["dev"]
    labels = ["Supported", "Refuted", "NEI", "NotAClaim"]
    rows = []
    for i, rec in enumerate(dev):
        gold = rec["label"]
        # Every third row gets a wrong-but-plausible prediction.
        wrong = next(label for label in labels if label != gold)
        pred = wrong if i % 3 == 2 else gold
        confidence = 0.55 + 0.04 * (i % 5)
        rows.append({
            "uid": rec["uid"],
            "pred": pred,
            "probs": {label: round((confidence if label == pred else
                                    (1 - confidence) / 3), 4) for label in labels},
        })
    write_jsonl(FIXTURES / "toy_clean" / "predictions_demo.jsonl", rows)

    # Retrieval fixtures: each dev claim has one relevant fact-check article.
    gold_rows, pred_rows = [], []
    corpus = [f"doc-{j:03d}" for j in range(20)]
    for i, rec in enumerate(dev):
        relevant = f"doc-{i:03d}"
        gold_rows.append({"uid": rec["uid"], "relevant_ids": [relevant]})
        ranked = [c for c in corpus if c != relevant][:9]
        # Place the right answer at rank 1, 3 or nowhere, in a fixed cycle.
        position = {0: 0, 1: 2}.get(i % 3)
        if position is not None:
            ranked.insert(position, relevant)
        pred_rows.append({
            "uid": rec["uid"],
            "ranked_ids": ranked[:10],
            "scores": [round(1.0 - 0.05 * j, 3) for j in range(len(ranked[:10]))],
        })
    write_jsonl(FIXTURES / "toy_clean" / "gold_retrieval_dev.jsonl", gold_rows)
    write_jsonl(FIXTURES / "toy_clean" / "predictions_retrieval_demo.jsonl", pred_rows)
    print(f"  {'demo preds':<12} classification={len(rows)}, retrieval={len(pred_rows)}")


def main() -> int:
    print("Writing fixtures to tests/fixtures/")
    clean = build("toy_clean", CLEAN)
    emit("toy_clean", clean, TEXTS["toy_clean"])
    leaky = plant_leaks(build("toy_leaky", CLEAN))
    emit("toy_leaky", leaky, TEXTS["toy_leaky"])
    emit_demo_predictions(clean)
    emit_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
