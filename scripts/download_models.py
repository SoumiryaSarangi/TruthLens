"""Fetch the Phase 2 models and the Dakshina transliteration benchmark.

    python scripts/download_models.py           # fetch what is missing
    python scripts/download_models.py --list    # sizes only, download nothing
    python scripts/download_models.py --only fasttext

Everything here is large and the hub connection drops often, so every fetch
resumes rather than restarting. Safe to kill and rerun at any point.

Two destinations, deliberately:

- `lid.176.bin` and Dakshina go to `data/raw/`, because they are *data* the
  splits and evals are built from, and `data/raw/DOWNLOADS.json` is the record
  of exactly which bytes a result came from.
- The transformer weights go to the HuggingFace cache (`HF_HOME`, redirected to
  D: in docs/environment.md), because transformers resolves them by model id
  and a second copy under data/raw/ would be 7 GB of duplication.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import sha256_file  # noqa: E402
from common.io_jsonl import load_json, write_json  # noqa: E402

RAW = Path("data/raw")
MANIFEST = RAW / "DOWNLOADS.json"

CHUNK = 1 << 20
MAX_ATTEMPTS = 40
UA = {"User-Agent": "truthlens-model-download"}

# -- Direct downloads ---------------------------------------------------------
FILES: dict[str, dict] = {
    "fasttext": {
        "homepage": "https://fasttext.cc/docs/en/language-identification.html",
        "licence": "CC BY-SA 3.0",
        "note": "lid.176 covers 176 languages. Trained largely on native-script "
                "web text, so romanized hi/pa is the hard case -- that is the "
                "point of measuring it (FR-3).",
        "files": {
            "lid.176.bin":
                "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin",
        },
    },
    "dakshina": {
        "homepage": "https://github.com/google-research-datasets/dakshina",
        "licence": "CC BY-SA 4.0",
        "note": "Romanized <-> native word and sentence pairs for 12 South Asian "
                "languages. The published benchmark for FR-5 transliteration.",
        "files": {
            "dakshina_dataset_v1.0.tar":
                "https://storage.googleapis.com/gresearch/dakshina/"
                "dakshina_dataset_v1.0.tar",
        },
    },
}

# -- HuggingFace repos --------------------------------------------------------
# Excludes keep this to the PyTorch weights: BGE-M3 alone ships ONNX and
# TensorFlow copies that would roughly double the download for nothing.
HF_EXCLUDE = ["*.onnx", "*.onnx_data", "onnx/*", "*.h5", "*.msgpack", "*.ot",
              "*.tflite", "openvino/*"]

HF_MODELS: dict[str, dict] = {
    "muril": {
        "repo_id": "google/muril-base-cased",
        "note": "Indic-focused BERT. Rung 3 of the embedding ladder.",
    },
    "labse": {
        "repo_id": "sentence-transformers/LaBSE",
        "note": "Bitext alignment and the t-SNE figure ONLY -- never retrieval "
                "(CLAUDE.md). Rung 4 of the ladder so the report can show why.",
    },
    "bge_m3": {
        "repo_id": "BAAI/bge-m3",
        "note": "The retrieval backbone (SYSTEM_DESIGN 10). Rung 5.",
    },
}


def human(n: float) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def _open(url: str, start: int = 0, timeout: int = 60):
    headers = dict(UA)
    if start:
        headers["Range"] = f"bytes={start}-"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def remote_size(url: str) -> int:
    """Content-Length without downloading the body."""
    request = urllib.request.Request(url, headers=UA, method="HEAD")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return int(response.headers.get("Content-Length") or 0)
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(1.5 * (attempt + 1))
    return 0


def fetch_resumable(url: str, dest: Path, expected: int) -> None:
    """Download with Range resumption. Safe to kill and rerun.

    Lifted from scripts/download_knowledge_store.py, which proved it against an
    11.5 GB file over this connection; the only change is taking a full URL
    instead of a path inside one HuggingFace repo.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    if dest.is_file() and (not expected or dest.stat().st_size == expected):
        print(f"  have   {dest.name}  {human(dest.stat().st_size)}")
        return

    have = part.stat().st_size if part.is_file() else 0
    started = time.time()
    stalls = 0

    while not expected or have < expected:
        try:
            with _open(url, start=have) as response, part.open("ab") as fh:
                if have and response.status != 206:
                    # A server that ignores Range restarts at 0; don't append twice.
                    fh.close()
                    part.unlink(missing_ok=True)
                    have = 0
                    raise urllib.error.URLError("server ignored Range; restarting")
                if not expected:
                    expected = have + int(response.headers.get("Content-Length") or 0)
                while chunk := response.read(CHUNK):
                    fh.write(chunk)
                    have += len(chunk)
                    if have % (64 << 20) < CHUNK:
                        pct = 100 * have / expected if expected else 0
                        rate = have / max(time.time() - started, 1e-6) / 1e6
                        print(f"    {pct:5.1f}%  {human(have)} / {human(expected)}  "
                              f"{rate:5.1f} MB/s", flush=True)
            stalls = 0
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            stalls += 1
            have = part.stat().st_size if part.is_file() else 0
            if stalls >= MAX_ATTEMPTS:
                raise RuntimeError(
                    f"{dest.name}: gave up after {stalls} reconnects at "
                    f"{human(have)} / {human(expected)}. Rerun to resume."
                ) from exc
            wait = min(2 ** min(stalls, 6), 60)
            print(f"    reconnect {stalls} at {human(have)} "
                  f"({type(exc).__name__}) - waiting {wait}s", flush=True)
            time.sleep(wait)

    part.replace(dest)
    print(f"  got    {dest.name}  {human(have)} in {(time.time() - started) / 60:.1f} min")


def record(manifest: dict, dataset: str, spec: dict, name: str, url: str, dest: Path) -> None:
    entry = manifest.setdefault(dataset, {})
    entry["homepage"] = spec.get("homepage", "")
    entry["licence"] = spec.get("licence", "")
    if spec.get("note"):
        entry["note"] = spec["note"]
    entry.setdefault("files", {})[name] = {
        "bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
        "url": url,
    }


def download_hf(key: str, spec: dict) -> str:
    """snapshot_download, which resumes on its own. Returns the local path."""
    from huggingface_hub import snapshot_download

    last: Exception | None = None
    for attempt in range(6):
        try:
            return snapshot_download(
                repo_id=spec["repo_id"],
                ignore_patterns=HF_EXCLUDE,
                max_workers=4,
            )
        except Exception as exc:
            last = exc
            wait = min(2 ** attempt * 5, 120)
            print(f"    {key}: attempt {attempt + 1} failed ({type(exc).__name__}); "
                  f"retrying in {wait}s -- partial files are kept", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{key} ({spec['repo_id']}): gave up after 6 attempts: {last}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/download_models.py")
    parser.add_argument("--list", action="store_true", help="print sizes and exit")
    parser.add_argument("--only", action="append", default=None,
                        help="fetch only these keys (repeatable)")
    args = parser.parse_args(argv)

    wanted = set(args.only) if args.only else None
    manifest = load_json(MANIFEST) if MANIFEST.is_file() else {}

    if args.list:
        for dataset, spec in FILES.items():
            for name, url in spec["files"].items():
                print(f"{dataset:10s} {name:32s} {human(remote_size(url))}")
        for key, spec in HF_MODELS.items():
            print(f"{key:10s} {spec['repo_id']:32s} (hub)")
        return 0

    for dataset, spec in FILES.items():
        if wanted and dataset not in wanted:
            continue
        print(f"{dataset}:")
        for name, url in spec["files"].items():
            dest = RAW / dataset / name
            fetch_resumable(url, dest, remote_size(url))
            record(manifest, dataset, spec, name, url, dest)
            write_json(MANIFEST, manifest)

    for key, spec in HF_MODELS.items():
        if wanted and key not in wanted:
            continue
        print(f"{key} ({spec['repo_id']}):", flush=True)
        path = download_hf(key, spec)
        print(f"  got    {spec['repo_id']} -> {path}", flush=True)

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
