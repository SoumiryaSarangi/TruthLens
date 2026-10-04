"""Choose the demo's Roman-Hindi chip by a rule fixed BEFORE any candidate is run.

    python scripts/pick_romanized_chip.py

Why: the first Roman-Hindi chip ("Sarkar ne announce kiya ... 6000 rupaye") is refuted
"High" from a fact-check about a US stimulus cheque: right verdict, evidence about a
different claim. The owner delegated the choice ("I just need the best results").

RULE (written before running; candidates are our own wording, never dataset text):
  A candidate QUALIFIES only if, through the served pipeline (configs/pipeline/dev.yaml,
  offline, no live search):
    1. it is detected as Hindi in Latin script and transliterated;
    2. its verdict equals its truth (false -> Refuted, true -> Supported) and it is NOT
       abstained;
    3. every source the card cites, and the first listed source, has BGE-M3 cosine >= 0.5
       with the claim (0.5 is the relevance floor the live path already uses).
  Among qualifying candidates the one with the highest MINIMUM cosine over those sources
  is chosen; ties go to the higher confidence.
  If none qualifies, the chip is NOT changed and the report's limitation example stays.

The rule is printed with every run; the whole candidate table is kept in
reports/romanized_chip_pick.json and summarised in docs/project-log.md, so the choice
among N candidates is disclosed, not hidden. This prints pipeline outputs; it computes
no metric and changes no reported number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FLOOR = 0.5
CANDIDATES = [
    ("Garam paani peene se corona khatam ho jata hai", "false"),
    ("Lehsun khane se corona virus theek ho jata hai", "false"),
    ("5G tower se corona virus failta hai", "false"),
    ("Kal se WhatsApp ke paise lagenge", "false"),
    ("Gaay ka mutra peene se cancer theek ho jata hai", "false"),
    ("Aadhaar card ko bank se link nahi kiya to account band ho jayega", "false"),
    ("Sarkar har ladki ko free scooty de rahi hai", "false"),
    ("Pyaaz sirhane rakhne se bukhaar utar jata hai", "false"),
    ("Vaccine lagwane se insaan napunsak ho jata hai", "false"),
    ("Bleach peene se corona theek ho jata hai", "false"),
    ("Taj Mahal Shah Jahan ne banwaya tha", "true"),
    ("Narendra Modi 2014 mein Bharat ke pradhan mantri bane", "true"),
    ("Pani mein haldi milakar peene se cancer jad se khatam ho jata hai", "false"),
    ("Mobile phone ki roshni se aankhen kharab nahi hoti", "true"),
]
WANT = {"false": "Refuted", "true": "Supported"}


def main() -> int:
    from pipeline.orchestrator import Orchestrator, PipelineConfig
    from retrieval.encoders import shared_encoder

    print(__doc__.split("RULE", 1)[1].split("The rule is printed", 1)[0].rstrip())
    cfg = PipelineConfig.load(ROOT / "configs/pipeline/dev.yaml")
    orch = Orchestrator(cfg)
    orch.verify("warm-up")
    encoder = shared_encoder("bge_m3")
    rows = []
    for text, truth in CANDIDATES:
        trace = orch.verify(text)
        res = trace.results[0] if trace.results else None
        pre = trace.pre
        row = {"text": text, "truth": truth, "qualifies": False}
        if res is None or pre is None:
            rows.append(row)
            continue
        by_id = {p.passage_id: p for p in res.passages}
        sources = [by_id[c] for c in res.cited if c in by_id]
        if res.passages and res.passages[0] not in sources:
            sources.append(res.passages[0])
        claim = res.claim.text
        vectors = encoder.encode([claim] + [p.text for p in sources], batch_size=16) if sources else []
        cosines = [float(sum(a * b for a, b in zip(vectors[0], v, strict=True))) for v in vectors[1:]]
        row.update({
            "lang": pre.lang, "script": pre.script, "transliterated": bool(pre.transliterated),
            "verdict": res.verdict, "abstained": res.abstained, "confidence": round(res.confidence, 3),
            "path": res.path, "sources": [(p.title or p.doc_id)[:70] for p in sources],
            "cosines": [round(c, 3) for c in cosines],
        })
        row["qualifies"] = bool(
            pre.lang == "hi" and pre.script == "latn" and pre.transliterated
            and res.verdict == WANT[truth] and not res.abstained
            and cosines and min(cosines) >= FLOOR)
        rows.append(row)
        print(f"{'QUALIFIES' if row['qualifies'] else 'no       '} {res.verdict:10} "
              f"abst={res.abstained!s:5} conf={res.confidence:.2f} min_cos={min(cosines, default=0):.2f} | {text}")
    winners = sorted((r for r in rows if r["qualifies"]),
                     key=lambda r: (-min(r["cosines"]), -r["confidence"]))
    out = {"rule_floor": FLOOR, "rows": rows, "chosen": winners[0]["text"] if winners else None}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "romanized_chip_pick.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nCHOSEN:", out["chosen"] or "none qualifies; the chip is unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
