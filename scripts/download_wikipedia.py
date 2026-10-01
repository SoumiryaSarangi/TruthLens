"""Fetch the Hindi and Punjabi Wikipedia article dumps, resumably.

    python scripts/download_wikipedia.py

The demo corpus's encyclopedia half (SYSTEM_DESIGN.md §14, decision D7). Only
the lead sections are used, and they are extracted by
`scripts/build_evidence_index.py`; this script only downloads.

The dump is PINNED to a dated snapshot, not `latest`: `latest` moves every
month, so the same command would fetch different bytes and the sha256 recorded
here would stop describing anything. Sizes were read from the live dump index
on 2026-09-30, not estimated:

    hiwiki-20260901-pages-articles.xml.bz2   240,367,815 bytes
    pawiki-20260901-pages-articles.xml.bz2    96,476,259 bytes

Wikimedia keeps dated dumps for a few months. If this snapshot has rotated off
the mirror, change DUMP_DATE, rerun, and the new sizes and hashes are recorded
in DOWNLOADS.json -- the corpus is a demo index, not an evaluation set, so a
newer snapshot changes no reported number.

Text is CC BY-SA 4.0; every passage the demo shows carries its article URL.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from common.hashing import sha256_file  # noqa: E402
from common.io_jsonl import load_json, write_json  # noqa: E402
from download_knowledge_store import fetch_resumable, free_bytes, human  # noqa: E402

DUMP_DATE = "20260901"
HOST = "https://dumps.wikimedia.org"
OUT = Path("data/raw/wikipedia")
MANIFEST = Path("data/raw/DOWNLOADS.json")

# Expected sizes are what makes the download resumable: `fetch_resumable` keeps
# going until it has exactly this many bytes, and refuses on any other count.
WIKIS: dict[str, int] = {
    "hiwiki": 240_367_815,
    "pawiki": 96_476_259,
}


def dump_name(wiki: str) -> str:
    return f"{wiki}-{DUMP_DATE}-pages-articles.xml.bz2"


def dump_url(wiki: str) -> str:
    return f"{HOST}/{wiki}/{DUMP_DATE}/{dump_name(wiki)}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/download_wikipedia.py")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    needed = sum(WIKIS.values())
    if free_bytes(OUT) < needed * 1.1:
        print(f"REFUSED: {human(needed)} needed, {human(free_bytes(OUT))} free.")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = load_json(MANIFEST) if MANIFEST.is_file() else {}
    entry = manifest.setdefault("wikipedia", {"files": {}})
    entry["repo"] = f"{HOST} ({DUMP_DATE} dumps)"
    entry["licence"] = "CC BY-SA 4.0 (attribution: article URL shown with every passage)"

    for wiki, expected in WIKIS.items():
        dest = OUT / dump_name(wiki)
        if args.force:
            dest.unlink(missing_ok=True)
        fetch_resumable(dump_name(wiki), dest, expected, url=dump_url(wiki))
        recorded = entry["files"].get(dest.name, {})
        if recorded.get("bytes") != expected or args.force:
            entry["files"][dest.name] = {
                "url": dump_url(wiki),
                "sha256": sha256_file(dest),
                "bytes": dest.stat().st_size,
            }
        write_json(MANIFEST, manifest)

    print(f"\nmanifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
