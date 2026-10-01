"""Build the demo evidence corpus: one global BM25 + BGE-M3 index.

    python scripts/build_evidence_index.py              # leads, then the index
    python scripts/build_evidence_index.py --stage leads
    python scripts/build_evidence_index.py --stage index

Decision D7 (SYSTEM_DESIGN.md §14): Hindi and Punjabi Wikipedia lead sections
plus the 78,077 MultiClaim fact-checks, searched by `retrieval/corpus.py` when a
forward has no AVeriTeC pool -- which is every real forward.

Inputs, all already on disk:

    data/raw/wikipedia/{hi,pa}wiki-*-pages-articles.xml.bz2   download_wikipedia.py
    data/interim/index/factcheck_meta.jsonl, ids.json         build_factcheck_bm25.py
    data/interim/index/bge_m3.npy                             build_factcheck_index.py

The fact-checks' BGE-M3 vectors are REUSED, not re-encoded: the same encoder at
the same 256-token CLS setting produced them, so re-encoding would spend ten
minutes to reproduce the same numbers. Only the leads are encoded.

Output, gitignored (fact-check text is MultiClaim's and must not be
redistributed):

    data/interim/evidence/
        leads_{hi,pa}.jsonl   extracted leads, kept so --stage index reruns fast
        docs.jsonl            one record per document; row i <-> vector i
        offsets.npy           byte offset of each record, for lazy reads
        bm25.npz, vocab.json  BM25Okapi weights (retrieval/corpus.py)
        bge_m3.npy            fp16, L2-normalised
        MANIFEST.json         what was built from what; the retriever checks it

Run it ALONE on this machine. Lead encoding is a GPU job, and Phase 5 measured
what two heavy jobs at once do to a 16 GB machine (56 -> 3 passages/s).
Resumable: encoded blocks are kept under `.partial/` and skipped on a rerun.
"""

from __future__ import annotations

import argparse
import bz2
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, load_jsonl  # noqa: E402
from data.wikilead import MAX_CHARS, article_url, iter_pages, lead  # noqa: E402

RAW = Path("data/raw/wikipedia")
FC_INDEX = Path("data/interim/index")
OUT = Path("data/interim/evidence")
LANGS = ("hi", "pa")
ENCODER, MAX_LENGTH = "bge_m3", 256
BLOCK = 8_192


def dump_path(lang: str) -> Path:
    found = sorted(RAW.glob(f"{lang}wiki-*-pages-articles.xml.bz2"))
    if not found:
        raise SystemExit(f"no {lang} dump under {RAW}. Run "
                         "`python scripts/download_wikipedia.py`.")
    return found[-1]


# -----------------------------------------------------------------------------
# Stage 1: leads
# -----------------------------------------------------------------------------


def extract_leads(lang: str) -> dict[str, int]:
    src = dump_path(lang)
    dest = OUT / f"leads_{lang}.jsonl"
    partial = dest.with_suffix(".jsonl.partial")
    stats = {"pages": 0, "articles": 0, "redirects": 0, "empty": 0, "kept": 0}
    started = time.time()
    with bz2.open(src, "rb") as stream, partial.open("w", encoding="utf-8") as fh:
        for page in iter_pages(stream):
            stats["pages"] += 1
            if page.namespace != 0:
                continue
            if page.redirect:
                stats["redirects"] += 1
                continue
            stats["articles"] += 1
            text = lead(page.wikitext)
            if not text:
                stats["empty"] += 1
                continue
            stats["kept"] += 1
            fh.write(json.dumps({
                "id": f"wiki:{lang}:{page.page_id}", "source": "wikipedia",
                "lang": lang, "title": page.title,
                "url": article_url(lang, page.title), "text": text,
            }, ensure_ascii=False) + "\n")
            if stats["kept"] % 50_000 == 0:
                print(f"    {lang}: {stats['kept']:,} leads "
                      f"({time.time() - started:.0f}s)", flush=True)
    partial.replace(dest)
    print(f"  {lang}: {stats} in {(time.time() - started) / 60:.1f} min")
    return stats


# -----------------------------------------------------------------------------
# Stage 2: the index
# -----------------------------------------------------------------------------


def factcheck_docs() -> list[dict]:
    """Fact-checks in the order of the existing vector matrix."""
    ids = load_json(FC_INDEX / "ids.json")["ids"]
    meta = {r["id"]: r for r in load_jsonl(FC_INDEX / "factcheck_meta.jsonl")}
    missing = [i for i in ids if i not in meta]
    if missing:
        raise SystemExit(f"{len(missing)} fact-check ids have no metadata "
                         f"(first: {missing[0]}). Rebuild the fact-check index.")
    return [{
        "id": f"fc:{i}", "source": "factcheck", "lang": meta[i].get("lang", ""),
        "title": meta[i].get("title") or "", "url": meta[i].get("url") or "",
        "publisher": meta[i].get("publisher") or "",
        "verdict": meta[i].get("verdict") or "", "text": meta[i]["text"],
    } for i in ids]


def encode_leads(texts: list[str]) -> np.ndarray:
    """BGE-M3 vectors for the leads, in resumable blocks."""
    from retrieval.encoders import build_encoder

    parts = OUT / ".partial"
    parts.mkdir(parents=True, exist_ok=True)
    encoder = None
    started = time.time()
    done_now = 0
    blocks = []
    for b, start in enumerate(range(0, len(texts), BLOCK)):
        path = parts / f"block_{b:04d}.npy"
        chunk = texts[start:start + BLOCK]
        if path.is_file() and np.load(path, mmap_mode="r").shape[0] == len(chunk):
            blocks.append(path)
            continue
        if encoder is None:
            encoder = build_encoder(ENCODER, max_length=MAX_LENGTH)
        vecs = encoder.encode(chunk, batch_size=64).astype(np.float16)
        tmp = path.with_suffix(".tmp.npy")
        np.save(tmp, vecs)
        tmp.replace(path)
        blocks.append(path)
        done_now += len(chunk)
        rate = done_now / max(time.time() - started, 1e-6)
        left = len(texts) - start - len(chunk)
        print(f"    {start + len(chunk):7,}/{len(texts):,}  {rate:5.0f} docs/s  "
              f"eta {left / max(rate, 1e-6) / 60:5.1f} min", flush=True)
    return np.vstack([np.load(p) for p in blocks]) if blocks else \
        np.empty((0, 1024), dtype=np.float16)


def build_index() -> dict:
    from retrieval.corpus import write_index

    fcs = factcheck_docs()
    leads = {lang: list(load_jsonl(OUT / f"leads_{lang}.jsonl")) for lang in LANGS}
    lead_docs = [d for lang in LANGS for d in leads[lang]]
    docs = fcs + lead_docs
    print(f"  documents: {len(fcs):,} fact-checks + "
          + " + ".join(f"{len(leads[lang]):,} {lang} leads" for lang in LANGS))

    fc_vectors = np.load(FC_INDEX / f"{ENCODER}.npy")
    if fc_vectors.shape[0] != len(fcs):
        raise SystemExit(f"fact-check vectors {fc_vectors.shape[0]} != ids {len(fcs)}")
    print("  encoding leads ...", flush=True)
    lead_vectors = encode_leads([d["text"] for d in lead_docs])

    downloads = load_json(Path("data/raw/DOWNLOADS.json")).get("wikipedia", {})
    print("  BM25 and writing ...", flush=True)
    manifest = write_index(
        OUT, docs, np.vstack([fc_vectors, lead_vectors]), ENCODER, MAX_LENGTH,
        built=datetime.now(UTC).isoformat(timespec="seconds"),
        lead_max_chars=MAX_CHARS,
        by_source={"factcheck": len(fcs),
                   **{f"wikipedia_{lang}": len(leads[lang]) for lang in LANGS}},
        dumps={lang: {"file": dump_path(lang).name,
                      "sha256": downloads.get("files", {})
                      .get(dump_path(lang).name, {}).get("sha256")}
               for lang in LANGS},
        excluded="AVeriTeC knowledge store (SYSTEM_DESIGN.md §14, D7)",
    )
    print(f"  wrote {OUT}: {manifest['by_source']}, vocab {manifest['vocab']:,}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/build_evidence_index.py")
    ap.add_argument("--stage", choices=("leads", "index", "all"), default="all")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage in ("leads", "all"):
        for lang in LANGS:
            extract_leads(lang)
    if args.stage in ("index", "all"):
        build_index()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
