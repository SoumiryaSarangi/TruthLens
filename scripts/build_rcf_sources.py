"""Build the source list for RC-F (docs/polarity-guard-protocol.md): real, simple, clearly rated fact-checked claims.

    python scripts/build_rcf_sources.py

Queries the Google Fact Check index through the project's own client (the key stays in .env and is never printed), keeps English claims of
6 to 22 words whose rating maps to Supported or Refuted, drops claims about a specific video, photo or post (a negation of those is not a claim
anyone would write), caps the number per publisher so no single outlet dominates, and writes data/private/rcf_sources.csv (git-ignored).
No system output is involved: this is the raw material the owner writes paraphrases and negations from.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

QUERIES = [
    "WhatsApp message free", "vaccine causes", "cancer cure", "lemon", "5G", "drinking water cures", "government scheme", "bank account closed",
    "RBI", "UPI", "Aadhaar", "PAN card", "petrol price", "election commission", "Supreme Court", "NASA", "moon", "earth", "COVID cure", "coronavirus home remedy",
    "diabetes cure", "garlic", "turmeric", "ginger", "heart attack", "mobile phone radiation", "microwave", "plastic rice", "fake eggs", "honey adulterated",
    "salt water", "hot water", "onion", "banana", "milk", "tea", "alcohol", "smoking", "sunlight", "vitamin", "India largest", "Indian railways", "ATM",
    "currency note", "GST", "income tax", "free recharge", "gas cylinder", "pension", "ration card", "scholarship", "lockdown", "mask", "flight", "Taj Mahal",
    "Great Wall", "lightning", "crore beneficiaries", "ISRO", "India record", "Supreme Court ruled", "scheme launched", "Indian army", "Olympics medal",
    "metro", "vaccination India", "monsoon", "population", "literacy", "electricity", "solar", "airport", "highway", "digital payments", "rail", "tax free",
    "myth", "banned", "new rule", "from April", "will be closed", "Rs 2000", "Rs 500", "free ration", "free laptop", "free scooty", "mobile number", "SIM card",
    "KYC", "e-challan", "driving licence", "helmet", "traffic fine", "FASTag", "toll", "Digi", "digital rupee", "net banking", "OTP", "link", "lottery", "KBC",
    "Amazon", "Flipkart", "Jio", "Airtel", "BSNL", "TRAI", "WhatsApp ban", "Telegram", "Instagram", "Facebook", "YouTube", "ChatGPT", "AI", "robot",
    "drinking", "eating", "sleep", "pregnant", "children", "elderly", "kidney", "liver", "eyes", "hair", "skin", "teeth", "blood", "bone", "lungs", "stomach",
    "papaya", "dengue", "malaria", "typhoid", "jaundice", "cholesterol", "blood pressure", "thyroid", "asthma", "allergy", "burn", "snake", "dog", "mosquito",
    "does not cause", "is safe", "is true", "is real", "confirmed", "genuine", "official", "correct claim", "cricket", "Parliament", "constitution", "Gandhi", "earthquake", "weather", "bats", "cow", "vegan", "coffee", "chocolate", "sugar", "oil", "tap water", "antibiotics", "tooth",
]
BAD = re.compile(r"\b(video|photo|photograph|image|picture|clip|viral post|screenshot|tweet|poster|footage|letter|notice|circular|says|said|claims?|claimed)\b", re.I)
# Politics and people (a negation would be a political statement), and bare statistics (a negation of a number is not natural).
SKIP = re.compile(r"\b(BJP|Congress|Modi|Rahul|Gandhi|Muslim|Hindu|Bihar|election|elections|vote|votes|voters|Wire|minister|party|crore|lakh|percent|mostly|Pahalgam|terror|terrorists)\b|%|\d{3,}", re.I)
PER_PUBLISHER = 5
TARGET = 70


def main() -> int:
    from data.verdicts import rating_to_verdict
    from retrieval.live.factcheck import GoogleFactCheck

    fc = GoogleFactCheck()
    if not fc.available:
        raise SystemExit("no Google Fact Check key configured (.env)")
    seen, rows, per_pub = set(), [], {}
    for q in QUERIES:
        try:
            hits = fc.search(q)
        except Exception as exc:  # a failed query is skipped, not fatal
            print(f"  query failed ({type(exc).__name__}): {q}")
            continue
        for h in hits:
            text = " ".join((h.claim_text or "").split())
            verdict = rating_to_verdict([h.rating]) if h.rating else None
            n = len(text.split())
            pub = (h.publisher or "").strip()
            key = text.lower()
            if (h.lang != "en" or verdict not in ("Supported", "Refuted") or not 6 <= n <= 22 or BAD.search(text) or SKIP.search(text) or key in seen
                    or not text.isascii() or per_pub.get(pub, 0) >= PER_PUBLISHER or not pub):
                continue
            seen.add(key)
            per_pub[pub] = per_pub.get(pub, 0) + 1
            rows.append({"claim_text": text, "rating": h.rating, "gold": "T" if verdict == "Supported" else "F", "publisher": pub, "url": h.url})
    trues = [r for r in rows if r["gold"] == "T"]
    falses = [r for r in rows if r["gold"] == "F"]
    keep = trues[:12] + falses[:max(0, TARGET - len(trues[:12]))]
    out = ROOT / "data" / "private" / "rcf_sources.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "claim_text", "rating", "gold", "publisher", "url"])
        w.writeheader()
        for i, r in enumerate(keep, 1):
            w.writerow({"source_id": i, **r})
    print(f"candidates {len(rows)} (T {len(trues)}, F {len(falses)}); kept {len(keep)}; publishers {sorted({r['publisher'] for r in keep})}")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
