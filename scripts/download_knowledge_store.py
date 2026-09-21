"""Fetch the AVeriTeC knowledge store from HuggingFace, resumably.

    python scripts/download_knowledge_store.py --split dev
    python scripts/download_knowledge_store.py --list

Separate from `scripts/download_data.py` because this is a different kind of
download: tens of gigabytes over a connection that drops. The claims file is
10 MB and either works or doesn't; this needs HTTP Range resumption, retries
with backoff, and the ability to be killed and restarted without losing work.

Sizes (measured from the HF API, not guessed):

    dev     11.54 GB   <- all Phase 1 needs
    train   63.52 GB   (3 files)
    test    40.71 GB   (test + test_updated)
    ALL    115.78 GB   does NOT fit in the 109 GB free on this machine

So the default is dev only. `--split train` is there for later phases and
prints the disk check before it starts.

The upstream repo builds this store by scraping via the Google Search API.
We download the prebuilt one instead: no API key, no scraping, no ToS
question, and everyone who uses it gets byte-identical evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import sha256_file  # noqa: E402
from common.io_jsonl import load_json, write_json  # noqa: E402

REPO = "chenxwh/AVeriTeC"

# hf.co, not huggingface.co. Same service, but on this connection the long
# hostname gets its TLS sessions reset almost every time (measured: 0/12
# success) while the short alias succeeds often enough to finish a resumable
# download. If hf.co ever starts failing too, try huggingface.co again before
# assuming the repo moved.
HOST = "https://hf.co"
API = f"{HOST}/api/models/{REPO}"
RESOLVE = f"{HOST}/{REPO}/resolve/main"

OUT = Path("data/raw/averitec_kb")
MANIFEST = OUT / "DOWNLOADS.json"

SPLITS: dict[str, list[str]] = {
    "dev": ["data_store/knowledge_store/dev_knowledge_store.zip"],
    "train": [
        "data_store/knowledge_store/train/train_0_999.zip",
        "data_store/knowledge_store/train/train_1000_1999.zip",
        "data_store/knowledge_store/train/train_2000_3067.zip",
    ],
}

CHUNK = 1 << 20          # 1 MiB
MAX_ATTEMPTS = 40        # the connection drops often; give up slowly
UA = {"User-Agent": "truthlens-kb-download"}


def _open(url: str, start: int = 0, timeout: int = 60):
    headers = dict(UA)
    if start:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def remote_sizes() -> dict[str, int]:
    """File sizes straight from the HF API, so nothing here is a guess."""
    last: Exception | None = None
    for attempt in range(8):
        try:
            with _open(f"{API}?blobs=true", timeout=40) as r:
                meta = json.loads(r.read())
            return {
                f["rfilename"]: (f.get("size") or 0)
                for f in meta.get("siblings", [])
            }
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"could not reach the HuggingFace API after 8 tries: {last}")


def human(n: float) -> str:
    return f"{n / 1e9:.2f} GB"


def fetch_resumable(path_in_repo: str, dest: Path, expected: int) -> None:
    """Download with Range resumption. Safe to kill and rerun."""
    url = f"{RESOLVE}/{path_in_repo}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    if dest.is_file() and dest.stat().st_size == expected:
        print(f"  have   {dest.name}  {human(expected)}")
        return

    have = part.stat().st_size if part.is_file() else 0
    started = time.time()
    stalls = 0

    while have < expected:
        try:
            with _open(url, start=have) as response, part.open("ab") as fh:
                # A server that ignores Range restarts at 0; don't append twice.
                if have and response.status != 206:
                    fh.close()
                    part.unlink(missing_ok=True)
                    have = 0
                    raise urllib.error.URLError("server ignored Range; restarting")
                while chunk := response.read(CHUNK):
                    fh.write(chunk)
                    have += len(chunk)
                    if have % (64 << 20) < CHUNK:
                        pct = 100 * have / expected
                        rate = have / max(time.time() - started, 1e-6) / 1e6
                        print(f"    {pct:5.1f}%  {human(have)} / {human(expected)}  "
                              f"{rate:5.1f} MB/s", flush=True)
            stalls = 0
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            stalls += 1
            have = part.stat().st_size if part.is_file() else 0
            if stalls >= MAX_ATTEMPTS:
                raise RuntimeError(
                    f"{path_in_repo}: gave up after {stalls} reconnects at "
                    f"{human(have)} / {human(expected)}. Rerun to resume."
                ) from exc
            wait = min(2 ** min(stalls, 6), 60)
            print(f"    reconnect {stalls} at {human(have)} "
                  f"({type(exc).__name__}) - waiting {wait}s", flush=True)
            time.sleep(wait)

    if have != expected:
        raise RuntimeError(f"{dest.name}: got {have} bytes, expected {expected}")
    part.replace(dest)
    print(f"  got    {dest.name}  {human(expected)} in {(time.time() - started) / 60:.1f} min")


def free_bytes(path: Path) -> int:
    import shutil
    target = path
    while not target.exists():
        target = target.parent
    return shutil.disk_usage(target).free


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/download_knowledge_store.py")
    ap.add_argument("--split", default="dev", choices=sorted(SPLITS))
    ap.add_argument("--list", action="store_true", help="show sizes and exit")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    sizes = remote_sizes()

    if args.list:
        print(f"\n{REPO} knowledge store\n")
        for split, files in SPLITS.items():
            total = sum(sizes.get(f, 0) for f in files)
            print(f"  {split:6} {len(files)} file(s)  {human(total)}")
        print(f"\n  free on this disk: {human(free_bytes(OUT))}")
        return 0

    files = SPLITS[args.split]
    needed = sum(sizes.get(f, 0) for f in files)
    already = sum((OUT / Path(f).name).stat().st_size
                  for f in files if (OUT / Path(f).name).is_file())
    free = free_bytes(OUT)

    print(f"\nAVeriTeC knowledge store - {args.split}")
    print(f"  download : {human(needed)} ({len(files)} file(s))")
    print(f"  free     : {human(free)}")
    if free < (needed - already) * 1.1:
        print("\nREFUSED: not enough free disk, with no margin for unzipping.")
        print("The zip is compressed JSON and expands several times over.")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = load_json(MANIFEST) if MANIFEST.is_file() else {}

    for path_in_repo in files:
        dest = OUT / Path(path_in_repo).name
        expected = sizes.get(path_in_repo, 0)
        if not expected:
            print(f"  SKIP {path_in_repo}: not in the remote listing")
            continue
        if args.force:
            dest.unlink(missing_ok=True)
        fetch_resumable(path_in_repo, dest, expected)
        manifest[dest.name] = {
            "repo": REPO,
            "path_in_repo": path_in_repo,
            "url": f"{RESOLVE}/{path_in_repo}",
            "bytes": dest.stat().st_size,
            "sha256": sha256_file(dest),
            "split": args.split,
        }
        write_json(MANIFEST, manifest)

    print(f"\nmanifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
