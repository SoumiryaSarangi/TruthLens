"""How much of the fact-check pool the verdict mapping can actually answer (FR-8).

    python scripts/report_verdict_coverage.py

Not a metric and not routed through the harness: it is a property of a lookup
table and a CSV, not of a model's predictions. It is a script rather than a
comment because the alternative is a number in prose that nobody re-derives when
`src/data/verdicts.py` changes.

Three questions, because they have different answers:

  pool      what share of the 78,077 indexed fact-checks could the fast path
            return a verdict for, if it matched them
  dev gold  what share of the fact-checks the dev queries actually point at --
            the number that bounds the fast path's usable coverage on the
            benchmark
  verdicts  the distribution over the 5 classes, which is the thing that must
            never be reported without, because fact-checks overwhelmingly debunk
            and an accuracy figure over this distribution is nearly meaningless
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, load_jsonl  # noqa: E402
from data.verdicts import (  # noqa: E402
    RATING_TO_VERDICT,
    first_instance_url,
    parse_ratings,
    publisher_from_url,
    rating_to_verdict,
)

RAW = Path("data/raw/multiclaim/fact_checks.csv")
IDS = Path("data/interim/index/ids.json")
GOLD = Path("data/gold/multiclaim_dev_retrieval.jsonl")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def report(top_unmapped: int = 25) -> int:
    if not RAW.is_file():
        print(f"missing {RAW}; MultiClaim is restricted and stays in data/raw/")
        return 2
    pool = set(load_json(IDS)["ids"]) if IDS.is_file() else set()
    gold: set[str] = set()
    if GOLD.is_file():
        for row in load_jsonl(GOLD):
            gold.update(row["relevant_ids"])

    groups = {"pool": pool, "dev gold": gold}
    mapped = collections.Counter()
    total = collections.Counter()
    verdicts: dict[str, collections.Counter] = {
        name: collections.Counter() for name in groups
    }
    unmapped = collections.Counter()
    no_url = collections.Counter()
    publishers = collections.Counter()

    with RAW.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fc_id = str(row["fact_check_id"])
            member = [name for name, ids in groups.items() if fc_id in ids]
            if not member:
                continue
            ratings = parse_ratings(row.get("ratings"))
            verdict = rating_to_verdict(ratings)
            url = first_instance_url(row.get("instances"))
            for name in member:
                total[name] += 1
                if verdict:
                    mapped[name] += 1
                    verdicts[name][verdict] += 1
                if not url:
                    no_url[name] += 1
            if verdict is None:
                for label in ratings:
                    if label not in RATING_TO_VERDICT:
                        unmapped[label] += 1
            if "pool" in member and url:
                publishers[publisher_from_url(url)] += 1

    for name in groups:
        if not total[name]:
            print(f"{name}: nothing to report (is the index built?)")
            continue
        print(f"\n{name}: {total[name]} fact-checks")
        print(f"  verdict mappable : {mapped[name]:6} = "
              f"{mapped[name] / total[name]:.1%}")
        print(f"  no URL           : {no_url[name]:6} = "
              f"{no_url[name] / total[name]:.1%}")
        if mapped[name]:
            print("  verdict distribution, over the MAPPED ones:")
            for verdict, count in verdicts[name].most_common():
                print(f"    {verdict:<12} {count:6} = {count / mapped[name]:6.1%}")

    print(f"\nmost common UNMAPPED ratings ({len(unmapped)} distinct):")
    for label, count in unmapped.most_common(top_unmapped):
        print(f"  {count:6}  {label!r}")
    print("\nmost common publishers in the pool:")
    for publisher, count in publishers.most_common(10):
        print(f"  {count:6}  {publisher}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/report_verdict_coverage.py")
    parser.add_argument("--top-unmapped", type=int, default=25)
    args = parser.parse_args(argv)
    return report(top_unmapped=args.top_unmapped)


if __name__ == "__main__":
    raise SystemExit(main())
