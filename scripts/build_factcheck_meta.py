"""Metadata sidecar for the fact-check index (FR-8).

    python scripts/build_factcheck_meta.py

Writes `data/interim/index/factcheck_meta.jsonl`, gitignored: derived from
restricted MultiClaim text.

## Why a sidecar rather than reading the CSV

`ids.json` maps an index row to a `fact_check_id` and nothing else, so a match
comes back as a bare id. But `FactCheckMatch` needs a title, a URL, a publisher,
a language and a verdict, and those live in a 493 MB CSV that takes the better
part of a minute to scan. NFR-1 budgets **3 s p95 for a fast-path response**;
scanning the corpus per request is not in that budget, and loading it once at
startup would put a minute in front of every `make serve`.

The sidecar is ~78k short rows. It is rebuilt whenever the pool or
`src/data/verdicts.py` changes, and it refuses to disagree with `ids.json` --
two indexes over different corpora produce scores that are not comparable, and
the difference would read as a result.
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, write_jsonl  # noqa: E402
from data.multiclaim import load_fact_checks  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from build_factcheck_index import fact_check_text  # noqa: E402

OUT = Path("data/interim/index")
META = OUT / "factcheck_meta.jsonl"
IDS = OUT / "ids.json"


def build(force: bool = False) -> int:
    if META.is_file() and not force:
        print(f"{META} exists; --force to rebuild")
        return 0
    if not IDS.is_file():
        print(f"missing {IDS}. Run scripts/build_factcheck_index.py first.")
        return 2

    started = time.time()
    ids = load_json(IDS)["ids"]
    fact_checks = load_fact_checks(ids=set(ids))
    missing = [i for i in ids if i not in fact_checks]
    if missing:
        print(f"REFUSING: {len(missing)} id(s) in {IDS} are absent from the CSV, "
              f"e.g. {missing[:3]}. The index and the metadata would describe "
              "different corpora.")
        return 2

    rows, verdicts = [], collections.Counter()
    for fc_id in ids:
        fc = fact_checks[fc_id]
        verdicts[fc.verdict or "(unmapped)"] += 1
        rows.append({
            "id": fc_id,
            # The claim is the searchable text; the title is what a user reads.
            "title": (fc.title or fc.claim or "")[:300],
            # What the index was built from, so a reranker reads exactly the
            # text the retriever matched on rather than a second variant of it.
            "text": fact_check_text(fc)[:1000],
            "url": fc.url,
            "publisher": fc.publisher,
            "verdict": fc.verdict,
            # `Lang` is en|hi|pa|other, and MultiClaim covers 39 languages.
            "lang": fc.lang or "other",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(META, rows)
    print(f"wrote {META}  n={len(rows)} in {time.time() - started:.1f}s")
    mapped = len(rows) - verdicts["(unmapped)"]
    print(f"  verdict mappable: {mapped}/{len(rows)} = {mapped / len(rows):.1%}")
    for verdict, count in verdicts.most_common():
        print(f"    {verdict:<12} {count:6}")
    langs = collections.Counter(r["lang"] for r in rows)
    print(f"  languages: {dict(langs.most_common())}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_factcheck_meta.py")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return build(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
