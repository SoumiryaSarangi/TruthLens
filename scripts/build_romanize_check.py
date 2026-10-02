"""How far synthetic romanization is from real typing (FR-26), as harness inputs.

    python scripts/build_romanize_check.py

The 33 hand-typed Punjabi forwards that carry a Gurmukhi rewrite are the only
place this project has the same message in native script AND as a person
actually typed it in Latin letters. Run backwards, they measure the romanizer
that built `x_claim_romanized`: input the Gurmukhi rewrite, compare against
what the person typed.

Writes (all gitignored):
  data/gold/handtyped_dev_romanize.jsonl        {uid, reference}: the typed text
  data/interim/handtyped/dev_native.jsonl       {uid, text}: the Gurmukhi rewrite,
                                                which `identity_transliteration`
                                                echoes (config `baseline_texts`)
  results/preds/p7_romanize_handtyped.jsonl      lexicon + rules
  results/preds/p7_romanize_handtyped_rules.jsonl  rules only (the ablation)

Both sides are lowercased: case is not transliteration, and the romanizer
emits lowercase. Nothing here is scored -- the configs
`p7_romanize_handtyped{,_rules}.yaml` are.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_jsonl, write_jsonl  # noqa: E402
from preprocess.romanize import romanize  # noqa: E402

NATIVE_GOLD = Path("data/gold/handtyped_dev_translit.jsonl")
TYPED = Path("data/interim/handtyped/dev.jsonl")


def main() -> int:
    native = {r["uid"]: r["reference"] for r in load_jsonl(NATIVE_GOLD)}
    typed = {r["uid"]: r["text"] for r in load_jsonl(TYPED)}
    uids = sorted(u for u in native if u in typed)
    write_jsonl(Path("data/gold/handtyped_dev_romanize.jsonl"),
                [{"uid": u, "reference": typed[u].lower()} for u in uids])
    write_jsonl(Path("data/interim/handtyped/dev_native.jsonl"),
                [{"uid": u, "text": native[u]} for u in uids])
    for name, lexicons in (("p7_romanize_handtyped", None),
                           ("p7_romanize_handtyped_rules", {})):
        write_jsonl(Path(f"results/preds/{name}.jsonl"),
                    [{"uid": u, "transliterated": romanize(native[u], lexicons).lower()}
                     for u in uids])
    print(f"{len(uids)} hand-typed pairs; wrote gold, baseline source and 2 prediction files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
