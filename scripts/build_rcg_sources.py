"""Source list for RC-G (docs/polarity-guard-v2-protocol.md): real, simple, clearly rated fact-checked claims NOT used by RC-F.

    python scripts/build_rcg_sources.py

Same index, same filters as build_rcf_sources.py (English claims of 6 to 22 words, a rating that maps to Supported or Refuted, no video/photo/post claims,
no politics or bare statistics, at most 5 per publisher), with a different set of queries, and every claim text already used by RC-F (the first list and
the curated 44) excluded. Writes data/private/rcg_sources.csv (git-ignored). The key stays in .env and is never printed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

QUERIES = [
    "hot lemon water", "bleach", "hydroxychloroquine", "ivermectin", "oxygen level", "steam inhalation", "camphor", "clove", "cinnamon", "neem",
    "aloe vera", "baking soda", "apple cider vinegar", "coconut oil", "ghee", "almonds", "dates", "jaggery", "cumin", "ajwain", "tulsi", "giloy",
    "kadha", "chyawanprash", "yoga", "cold water", "ice", "fridge", "AC", "fan", "power bank", "charger", "battery blast", "mobile explosion",
    "earphones", "laptop", "internet", "Google", "Gmail", "password", "hacked", "phishing", "scam call", "fake website", "online fraud", "QR code",
    "Paytm", "PhonePe", "Google Pay", "credit card", "debit card", "loan app", "insurance", "LIC", "EPFO", "provident fund", "Ayushman", "Jan Dhan",
    "Mudra", "Ujjwala", "PM Kisan", "Kisan", "farmers", "MSP", "fertilizer", "drought", "flood", "cyclone", "tsunami", "meteor", "asteroid", "eclipse",
    "solar eclipse", "full moon", "comet", "Mars", "ISS", "satellite", "rocket", "Chandrayaan", "Mangalyaan", "Gaganyaan", "railway ticket", "Tatkal",
    "IRCTC", "train", "bus", "auto", "metro fare", "airline", "airport rule", "passport", "visa", "driving", "licence", "number plate", "RC", "insurance renewal",
    "hospital", "doctor", "nurse", "blood donation", "organ", "kidney stone", "gallstone", "ulcer", "acidity", "gas", "constipation", "piles", "arthritis",
    "back pain", "migraine", "stroke", "heart", "pulse", "BP", "sugar level", "insulin", "cancer risk", "mammogram", "pap smear", "HPV", "polio", "measles",
    "TB", "HIV", "hepatitis", "rabies", "snake bite", "scorpion", "dog bite", "bee", "spider", "crocodile", "tiger", "elephant", "monkey", "peacock",
]


def main() -> int:
    import build_rcf_sources as b
    from data.verdicts import rating_to_verdict
    from retrieval.live.factcheck import GoogleFactCheck

    used = set()
    for name in ("rcf_sources.csv", "rcf_sources_final.csv"):
        path = ROOT / "data" / "private" / name
        if path.exists():
            with path.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    used.add((r.get("claim_text") or r.get("source_claim") or "").lower())
    fc = GoogleFactCheck()
    if not fc.available:
        raise SystemExit("no Google Fact Check key configured (.env)")
    seen, rows, per_pub = set(used), [], {}
    for q in QUERIES:
        try:
            hits = fc.search(q)
        except Exception as exc:
            print(f"  query failed ({type(exc).__name__}): {q}")
            continue
        for h in hits:
            text = " ".join((h.claim_text or "").split())
            verdict = rating_to_verdict([h.rating]) if h.rating else None
            n = len(text.split())
            pub = (h.publisher or "").strip()
            if (h.lang != "en" or verdict not in ("Supported", "Refuted") or not 6 <= n <= 22 or b.BAD.search(text) or b.SKIP.search(text)
                    or text.lower() in seen or not text.isascii() or per_pub.get(pub, 0) >= b.PER_PUBLISHER or not pub):
                continue
            seen.add(text.lower())
            per_pub[pub] = per_pub.get(pub, 0) + 1
            rows.append({"claim_text": text, "rating": h.rating, "gold": "T" if verdict == "Supported" else "F", "publisher": pub, "url": h.url})
    out = ROOT / "data" / "private" / "rcg_sources.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "claim_text", "rating", "gold", "publisher", "url"])
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow({"source_id": i, **r})
    print(f"excluded {len(used)} RC-F claims; candidates {len(rows)} (T {sum(r['gold'] == 'T' for r in rows)}, F {sum(r['gold'] == 'F' for r in rows)})")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
