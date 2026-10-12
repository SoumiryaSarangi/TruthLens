"""Pack the git-ignored files the served application needs into one archive, to copy to a deployment machine.

    python scripts/package_runtime.py --dry-run               # list what would go in, with sizes
    python scripts/package_runtime.py --out dist/truthlens-runtime.zip

The repository (git) holds the code and the configs; the served application also reads data that is rebuilt, not committed:
the fact-check index, the demo evidence corpus, the small trained adapters, the language-ID model and the transliteration
lexicon. This script gathers exactly those, preserving their relative paths, so unpacking the archive at the root of a
fresh checkout makes it complete. It does NOT include `.env` (the API key travels separately, never in an archive), the
Hugging Face model cache (models download on first use; see docs/DEPLOYMENT.md) or any dataset used only for evaluation.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (path, why). A directory is included whole; a file by itself.
PAYLOAD: list[tuple[str, str]] = [
    ("data/interim/index/bge_m3.npy", "fact-check index: embeddings"),
    ("data/interim/index/factcheck_meta.jsonl", "fact-check index: publisher, rating, url, claim text"),
    ("data/interim/index/ids.json", "fact-check index: ids"),
    ("data/interim/index/bm25_corpus.jsonl", "fact-check index: lexical corpus"),
    ("data/interim/evidence", "demo evidence corpus (hi/pa Wikipedia leads plus fact-checks) and its indexes"),
    ("data/interim/models/aggregator_xlmr_nli_prior", "aggregator served by configs/pipeline/dev.yaml"),
    ("data/interim/models/checkworthy_xlmr", "check-worthiness adapter"),
    ("data/interim/models/span_xlmr_joint", "claim span adapter"),
    ("data/interim/models/explainer_indicbart", "explanation generator adapter"),
    ("data/interim/models/roman_lid.joblib", "romanized language-ID model"),
    ("data/raw/fasttext/lid.176.bin", "fastText language ID"),
    ("data/raw/dakshina/extracted", "transliteration lexicon"),
]


def collect() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for rel, _why in PAYLOAD:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"missing: {rel} (run `make data` and the build scripts, or copy it from the development machine)")
        if p.is_dir():
            files += [(f, f.relative_to(ROOT).as_posix()) for f in sorted(p.rglob("*")) if f.is_file()]
        else:
            files.append((p, rel))
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="dist/truthlens-runtime.zip")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    files = collect()
    total = sum(f.stat().st_size for f, _ in files)
    for rel, why in PAYLOAD:
        size = sum(f.stat().st_size for f, name in files if name == rel or name.startswith(rel + "/"))
        print(f"  {size / 1e6:9.1f} MB  {rel}   ({why})")
    print(f"{len(files)} files, {total / 1e9:.2f} GB uncompressed")
    if args.dry_run:
        return 0
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as zf:
        for f, name in files:
            zf.write(f, name)
    print(f"wrote {out} ({out.stat().st_size / 1e9:.2f} GB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
