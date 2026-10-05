"""POST HOC simulation (docs/silence-diagnosis-protocol.md): how many silent claims would a looser title gate let through to the models?

Titles only, no model run. Variants were NOT pre-registered.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from pipeline.live import _PARENS, _WORD, TITLE_GENERIC, _same_word, title_grounded  # noqa: E402


def words(title):
    return [w for w in _WORD.findall(_PARENS.sub(" ", title).lower()) if w not in TITLE_GENERIC]

def claimset(forms):
    return {w for f in forms if f.isascii() for w in _WORD.findall(f.lower())}

def prefix_same(a, b):
    if _same_word(a, b):
        return True
    n = min(len(a), len(b))
    return n >= 4 and (a.startswith(b[:n]) or b.startswith(a[:n]))

def v1(title, forms):
    w, c = words(title), claimset(forms)
    return bool(w) and all(any(prefix_same(x, y) for y in c) for x in w)

def acro(title, c):
    ws = [x for x in re.findall(r"[a-z]+", title.lower()) if x not in ("of", "the", "and", "for", "in")]
    return len(ws) >= 2 and "".join(x[0] for x in ws) in c

def v4(title, forms):
    c = claimset(forms)
    return v1(title, forms) or acro(title, c)

def v3(title, forms):
    w, c = words(title), claimset(forms)
    if not w:
        return False
    hit = [any(prefix_same(x, y) for y in c) for x in w]
    return (sum(hit) / len(w) >= 2 / 3 and hit[0]) or all(hit)

V = {"V0 current": title_grounded, "V1 +stem": v1, "V3 +2/3 incl. head word": v3, "V4 +stem+acronym": v4}
tot = collections.Counter()
ex = collections.defaultdict(list)
n = collections.Counter()
for w in ("b", "a1"):
    for line in (ROOT / "reports" / "real_claims" / f"diag_{w}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["gold"] == "U":
            continue
        ps = [p for p in r["diag"].get("passages", []) if p["source"] == "wikipedia" and p["retrieval"] >= 0.5]
        silent = ps and not any(p.get("stance") for p in r["diag"]["passages"])
        n[w] += 1
        if not silent:
            continue
        forms = [r["diag"].get("claim_en") or "", r["text"]]
        for k, f in V.items():
            hit = [p["title"] for p in ps if f(p["title"], forms)]
            if hit:
                tot[(w, k)] += 1
                if k != "V0 current" and len(ex[k]) < 40:
                    ex[k].append((r["gold"], (forms[0] or r["text"])[:70], hit[:2]))
print(n)
for k in V:
    print(k, {w: tot[(w, k)] for w in ("b", "a1")})
for k in ("V1 +stem", "V4 +stem+acronym", "V3 +2/3 incl. head word"):
    print("\n", k)
    for e in ex[k][:14]:
        print("  ", e)
