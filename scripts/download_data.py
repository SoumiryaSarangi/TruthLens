"""Fetch the open-access source datasets into data/raw/.

    python scripts/download_data.py            # fetch what is missing
    python scripts/download_data.py --list     # show sources without downloading
    python scripts/download_data.py --force    # re-fetch everything

Only open-access datasets live here. MultiClaim is access-restricted on Zenodo
and CheckThat! 2025 Task 2 requires registration, so neither is automated --
see data/CLAUDE.md for their manual steps.

Every downloaded file's sha256 is recorded in data/raw/DOWNLOADS.json. That is
what lets a split built six weeks from now be traced back to exactly the bytes
it came from, even if upstream quietly re-releases a file.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import sha256_file  # noqa: E402
from common.io_jsonl import load_json, write_json  # noqa: E402

RAW = Path("data/raw")
MANIFEST = RAW / "DOWNLOADS.json"

GH = "https://raw.githubusercontent.com"

# X-CLAIM ships six languages; we take only the three this project covers.
# The en2xx files are MACHINE TRANSLATED English, deliberately not fetched:
# the X-CLAIM paper's own finding is that joint multilingual training beats
# training on English-translated data, and mixing them in by accident would
# quietly undermine the ablation that replicates it.
XCLAIM_LANGS = ("en", "hi", "pa")
XCLAIM_SPLITS = ("train", "dev", "test")

SOURCES: dict[str, dict] = {
    "averitec": {
        "homepage": "https://fever.ai/dataset/averitec.html",
        "repo": "https://github.com/MichSchli/AVeriTeC",
        "licence": "CC BY-NC 4.0 (non-commercial; academic use)",
        "note": "Only train and dev are public; the test split is held out for "
                "the FEVER shared task.",
        "files": {
            "train.json": f"{GH}/MichSchli/AVeriTeC/main/data/train.json",
            "dev.json": f"{GH}/MichSchli/AVeriTeC/main/data/dev.json",
        },
    },
    "x_claim": {
        "homepage": "https://aclanthology.org/2023.emnlp-main.236/",
        "repo": "https://github.com/mbzuai-nlp/x-claim",
        "licence": "see repo; EMNLP 2023 research release",
        "note": "en/hi/pa only. The en2xx machine-translated files are "
                "deliberately not fetched.",
        "files": {
            f"{split}-{lang}.csv": f"{GH}/mbzuai-nlp/x-claim/main/data/{split}-{lang}.csv"
            for lang in XCLAIM_LANGS
            for split in XCLAIM_SPLITS
        },
    },
}


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "truthlens-download"})
    with urllib.request.urlopen(request, timeout=120) as response:
        dest.write_bytes(response.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/download_data.py")
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    parser.add_argument("--list", action="store_true", help="print sources and exit")
    parser.add_argument("--only", help="fetch a single dataset by name")
    args = parser.parse_args(argv)

    if args.list:
        for name, spec in SOURCES.items():
            print(f"\n{name}  ({len(spec['files'])} files)")
            print(f"  repo:    {spec['repo']}")
            print(f"  licence: {spec['licence']}")
            print(f"  note:    {spec['note']}")
        return 0

    manifest = load_json(MANIFEST) if MANIFEST.is_file() else {}
    failures: list[str] = []

    for name, spec in SOURCES.items():
        if args.only and name != args.only:
            continue
        print(f"\n{name}")
        entry = manifest.setdefault(name, {"repo": spec["repo"],
                                           "licence": spec["licence"],
                                           "files": {}})
        entry["repo"] = spec["repo"]
        entry["licence"] = spec["licence"]

        for filename, url in spec["files"].items():
            dest = RAW / name / filename
            if dest.is_file() and not args.force:
                print(f"  have  {filename}")
                continue
            try:
                fetch(url, dest)
            except (urllib.error.URLError, OSError) as exc:
                print(f"  FAIL  {filename}: {exc}")
                failures.append(f"{name}/{filename}")
                continue
            digest = sha256_file(dest)
            entry["files"][filename] = {
                "url": url,
                "sha256": digest,
                "bytes": dest.stat().st_size,
            }
            print(f"  got   {filename:<16} {dest.stat().st_size / 1e6:>7.2f} MB  {digest[:12]}")

    # Backfill hashes for files that were already on disk.
    for name, spec in SOURCES.items():
        entry = manifest.get(name)
        if not entry:
            continue
        for filename in spec["files"]:
            dest = RAW / name / filename
            if dest.is_file() and filename not in entry["files"]:
                entry["files"][filename] = {
                    "url": spec["files"][filename],
                    "sha256": sha256_file(dest),
                    "bytes": dest.stat().st_size,
                }

    write_json(MANIFEST, manifest)
    print(f"\nmanifest: {MANIFEST}")
    if failures:
        print(f"FAILED: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
