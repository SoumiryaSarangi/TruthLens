"""Flatten the AVeriTeC knowledge store zip into a compact per-claim cache.

    python scripts/build_kb_cache.py --split dev

One pass over the 11.5 GB zip, writing
`data/interim/averitec_kb_dev/{claim_idx}.jsonl`, one line per candidate
document:

    {"doc_id": "<url>", "is_gold": true, "paragraphs": ["...", "..."]}

Why this exists: parsing the zip costs 15-40 minutes every time something
downstream wants evidence. Paying it once turns every later retrieval run into
seconds, which is the difference between one experiment a day and ten.

**Truncation is a real modelling choice, not a shortcut.** Each document is cut
to `--max-doc-chars` (default 4000). Measured on this data: BM25 over untruncated
documents takes 4.6 s per claim (~38 min for dev), against 0.64 s truncated
(~5 min). The cut is a parameter precisely so its cost can be measured -- rebuild
at a different N, rerun the eval, and the change in Recall@k is the answer.
Whatever value produced a number is recorded in the cache's MANIFEST.json and
belongs in the results table beside it.

Paragraphs are kept as a list rather than joined, because the stance stage picks
the single best paragraph per document to feed NLI (512-token limit) and the UI
highlights it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import write_json, write_jsonl  # noqa: E402

ZIP = Path("data/raw/averitec_kb/dev_knowledge_store.zip")
OUT_ROOT = Path("data/interim")
DEFAULT_MAX_DOC_CHARS = 4000


def claim_members(z: zipfile.ZipFile) -> dict[int, str]:
    """Map claim index -> member name, e.g. 133 -> 'output_dev/133.json'."""
    out: dict[int, str] = {}
    for name in z.namelist():
        if not name.endswith(".json"):
            continue
        stem = name.rsplit("/", 1)[-1].removesuffix(".json")
        if stem.isdigit():
            out[int(stem)] = name
    return out


def build(split: str, max_doc_chars: int, limit: int | None = None) -> int:
    if not ZIP.is_file():
        print(f"missing {ZIP}. Run `make kb` first.")
        return 2

    out_dir = OUT_ROOT / f"averitec_kb_{split}"
    out_dir.mkdir(parents=True, exist_ok=True)

    z = zipfile.ZipFile(ZIP)
    members = claim_members(z)
    todo = sorted(members)[:limit] if limit else sorted(members)

    print(f"{len(todo)} claims -> {out_dir}  (max_doc_chars={max_doc_chars})")
    started = time.time()
    total_docs = total_gold = 0
    no_gold: list[int] = []

    for n, idx in enumerate(todo, start=1):
        with z.open(members[idx]) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]

        # One entry per URL. A URL can appear under several `type` values; if
        # any of them is "gold" the document is gold, so fold rather than
        # first-wins -- otherwise a gold document found by two search
        # strategies could be recorded as a distractor.
        docs: dict[str, dict] = {}
        for r in rows:
            url = r.get("url")
            if not url:
                continue
            entry = docs.get(url)
            if entry is None:
                text = r.get("url2text") or []
                entry = {"doc_id": url, "is_gold": False, "paragraphs": text}
                docs[url] = entry
            if r.get("type") == "gold":
                entry["is_gold"] = True

        out_rows = []
        for entry in docs.values():
            kept, used = [], 0
            for para in entry["paragraphs"]:
                if used >= max_doc_chars:
                    break
                para = para[: max_doc_chars - used]
                if para:
                    kept.append(para)
                    used += len(para)
            out_rows.append({"doc_id": entry["doc_id"], "is_gold": entry["is_gold"],
                             "paragraphs": kept})

        write_jsonl(out_dir / f"{idx}.jsonl", out_rows)
        gold = sum(1 for r in out_rows if r["is_gold"])
        total_docs += len(out_rows)
        total_gold += gold
        if gold == 0:
            no_gold.append(idx)

        if n % 25 == 0 or n == len(todo):
            rate = n / max(time.time() - started, 1e-6)
            eta = (len(todo) - n) / max(rate, 1e-6) / 60
            print(f"  {n:4}/{len(todo)}  {rate:4.1f} claims/s  eta {eta:5.1f} min", flush=True)

    write_json(out_dir / "MANIFEST.json", {
        "split": split,
        "source_zip": ZIP.as_posix(),
        "max_doc_chars": max_doc_chars,
        "n_claims": len(todo),
        "n_docs": total_docs,
        "n_gold": total_gold,
        "claims_without_gold": no_gold,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    mins = (time.time() - started) / 60
    print(f"\n  {len(todo)} claims, {total_docs} docs, {total_gold} gold, "
          f"{mins:.1f} min")
    print(f"  docs/claim {total_docs / max(len(todo), 1):.0f}  "
          f"gold/claim {total_gold / max(len(todo), 1):.2f}")
    if no_gold:
        print(f"  WARNING: {len(no_gold)} claim(s) have no gold document and cannot "
              f"be scored for retrieval: {no_gold[:10]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/build_kb_cache.py")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--max-doc-chars", type=int, default=DEFAULT_MAX_DOC_CHARS)
    ap.add_argument("--limit", type=int, default=None, help="first N claims only (smoke test)")
    args = ap.parse_args(argv)
    return build(args.split, args.max_doc_chars, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
