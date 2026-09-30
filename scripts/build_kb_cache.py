"""Flatten an AVeriTeC knowledge store into a compact per-claim cache.

    python scripts/build_kb_cache.py --split dev
    python scripts/build_kb_cache.py --split train     # 3 archives, 63.5 GB

Writes `data/interim/averitec_kb_{split}/{claim_idx}.jsonl`, one line per
candidate document:

    {"doc_id": "<url>", "is_gold": true, "paragraphs": ["...", "..."]}

Why this exists: parsing a zip costs 15-40 minutes every time something
downstream wants evidence. Paying it once turns every later retrieval run into
seconds, which is the difference between one experiment a day and ten.

**Truncation is a real modelling choice, not a shortcut.** Each document is cut
to `--max-doc-chars` (default 4000). Measured on this data: BM25 over untruncated
documents takes 4.6 s per claim (~38 min for dev), against 0.64 s truncated
(~5 min). The cut is a parameter precisely so its cost can be measured -- rebuild
at a different N, rerun the eval, and the change in Recall@k is the answer.
Whatever value produced a number is recorded in the cache's MANIFEST.json and
belongs in the results table beside it. Train and dev use the same value so their
numbers stay comparable.

Paragraphs are kept as a list rather than joined, because the stance stage picks
the single best passage per document and the UI highlights it.

## What this refuses to do, and why each one matters

Until Phase 5 this script hard-coded the DEV archive. `--split train` would have
read the dev zip and written it into `averitec_kb_train/` without a word. Now:

* **No fallback to another split's archive.** `src/retrieval/kb.py` holds the one
  map of which archives form which split.
* **No incomplete download.** An archive counts only if `DOWNLOADS.json` records
  it with a matching size -- the downloader writes that entry after it finishes,
  so a truncated file cannot pass.
* **No half-built cache.** It builds into `averitec_kb_{split}.partial/` and
  renames at the end, so an interrupted run can never satisfy
  `KnowledgeStore.has_cache` and quietly serve a store missing half its claims.
* **No unverified claim-to-file mapping.** Two checks, one per failure mode: each
  member's internal `claim_id` must equal the index it was filed under, and each
  claim's gold documents must overlap the source URLs of that claim's own QA
  annotations. Measured on dev: 500/500 claims agree with their own annotations
  against 13/500 for the neighbouring claim -- so an off-by-one mapping cannot
  pass the second check even if it passed the first.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.io_jsonl import load_json, write_json, write_jsonl  # noqa: E402
from retrieval.kb import (  # noqa: E402
    KB_RAW,
    KnowledgeStoreMissing,
    resolve_members,
    split_zips,
)

OUT_ROOT = Path("data/interim")
RAW_AVERITEC = Path("data/raw/averitec")
DEFAULT_MAX_DOC_CHARS = 4000

# The mapping check. Own-claim agreement is measured at 1.00 on dev; a mapping
# shifted by one lands near 0.03. Wide margins on both sides, so a real change
# in the data is what trips it, not noise.
MIN_OWN_AGREEMENT = 0.95
MAX_NEIGHBOUR_AGREEMENT = 0.20


def check_downloads(split: str, raw_root: Path | None = None) -> list[str]:
    """Problems that make an archive untrustworthy; empty means go.

    `raw_root` resolves at CALL time, not as a default argument, which would bind
    the module-level path when the function is defined and ignore any later
    change to it.
    """
    raw_root = Path(raw_root) if raw_root is not None else KB_RAW
    manifest_path = raw_root / "DOWNLOADS.json"
    manifest = load_json(manifest_path) if manifest_path.is_file() else {}
    problems = []
    for path, _, _ in split_zips(split, raw_root):
        entry = manifest.get(path.name)
        if entry is None:
            problems.append(f"{path.name} is not in {manifest_path}; the downloader "
                            "records a file only after it completes")
        elif int(entry.get("bytes", -1)) != path.stat().st_size:
            problems.append(f"{path.name} is {path.stat().st_size} bytes on disk but "
                            f"{entry.get('bytes')} in the manifest")
    return problems


def qa_source_urls(split: str) -> dict[int, set[str]]:
    """claim index -> the URLs its own QA annotations cite."""
    path = RAW_AVERITEC / f"{split}.json"
    if not path.is_file():
        return {}
    claims = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, set[str]] = {}
    for i, claim in enumerate(claims):
        urls = set()
        for q in claim.get("questions") or []:
            for a in q.get("answers") or []:
                for key in ("source_url", "cached_source_url"):
                    if a.get(key):
                        urls.add(a[key])
        out[i] = urls
    return out


def _normal(url: str) -> str:
    """Compare URLs without the archive.org wrapper, scheme or trailing slash."""
    if "web.archive.org/web/" in url:
        url = url.split("/", 5)[-1] if url.count("/") >= 5 else url
    url = url.split("://", 1)[-1]
    return url.rstrip("/").lower()


def agreement(gold: dict[int, set[str]], qa: dict[int, set[str]], shift: int) -> float:
    """Share of claims whose gold overlaps the QA URLs of claim `idx + shift`."""
    scored = hits = 0
    for idx, urls in gold.items():
        other = qa.get(idx + shift)
        if not urls or other is None:
            continue
        scored += 1
        hits += bool({_normal(u) for u in urls} & {_normal(u) for u in other})
    return hits / scored if scored else 0.0


def build(split: str, max_doc_chars: int, limit: int | None = None,
          force: bool = False) -> int:
    try:
        problems = check_downloads(split)
    except (KnowledgeStoreMissing, ValueError) as exc:
        print(f"REFUSED: {exc}")
        return 2
    if problems:
        print("REFUSED: the archives are not a verified complete download:")
        for p in problems:
            print(f"  - {p}")
        return 2

    final = OUT_ROOT / f"averitec_kb_{split}"
    partial = OUT_ROOT / f"averitec_kb_{split}.partial"
    if final.exists() and not force and not limit:
        print(f"REFUSED: {final} exists. --force to rebuild it.")
        return 2
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)

    members = resolve_members(split)
    todo = sorted(members)[:limit] if limit else sorted(members)
    zips: dict[str, zipfile.ZipFile] = {}

    print(f"{len(todo)} claims from {len({z for z, _ in members.values()})} "
          f"archive(s) -> {final}  (max_doc_chars={max_doc_chars})")
    started = time.time()
    total_docs = total_gold = total_empty_gold = 0
    no_gold: list[int] = []
    gold_urls: dict[int, set[str]] = {}
    id_mismatch: list[int] = []

    for n, idx in enumerate(todo, start=1):
        zip_path, member = members[idx]
        if zip_path not in zips:
            zips[zip_path] = zipfile.ZipFile(zip_path)
        with zips[zip_path].open(member) as fh:
            rows = [json.loads(line) for line in fh if line.strip()]

        # The archives store claim_id as a STRING ("0", not 0). Compared as an
        # int, every member of a known-good store fails -- which is how the first
        # version of this check refused all 60 claims of a dev smoke build.
        if any(r.get("claim_id") is not None and str(r["claim_id"]) != str(idx)
               for r in rows):
            id_mismatch.append(idx)

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
                entry = {"doc_id": url, "is_gold": False,
                         "paragraphs": r.get("url2text") or []}
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

        write_jsonl(partial / f"{idx}.jsonl", out_rows)
        gold = [r for r in out_rows if r["is_gold"]]
        gold_urls[idx] = {r["doc_id"] for r in gold}
        total_docs += len(out_rows)
        total_gold += len(gold)
        total_empty_gold += sum(1 for r in gold if not "".join(r["paragraphs"]).strip())
        if not gold:
            no_gold.append(idx)

        if n % 25 == 0 or n == len(todo):
            rate = n / max(time.time() - started, 1e-6)
            eta = (len(todo) - n) / max(rate, 1e-6) / 60
            print(f"  {n:4}/{len(todo)}  {rate:4.1f} claims/s  eta {eta:5.1f} min",
                  flush=True)

    for z in zips.values():
        z.close()

    # -- the mapping checks, before anything is renamed into place --------------
    if id_mismatch:
        print(f"REFUSED: {len(id_mismatch)} member(s) carry a claim_id that disagrees "
              f"with the index they were filed under, e.g. {id_mismatch[:5]}. "
              f"Left the partial build at {partial}.")
        return 2
    qa = qa_source_urls(split)
    own = agreement(gold_urls, qa, 0)
    neighbour = agreement(gold_urls, qa, 1)
    print(f"  mapping check: gold URLs agree with the claim's OWN QA sources for "
          f"{own:.1%}, with the NEIGHBOUR's for {neighbour:.1%}")
    if qa and (own < MIN_OWN_AGREEMENT or neighbour > MAX_NEIGHBOUR_AGREEMENT):
        print(f"REFUSED: expected own >= {MIN_OWN_AGREEMENT:.0%} and neighbour <= "
              f"{MAX_NEIGHBOUR_AGREEMENT:.0%}. The claim-to-file mapping is not the "
              f"one this code assumes. Left the partial build at {partial}.")
        return 2

    write_json(partial / "MANIFEST.json", {
        "split": split,
        "source_zips": sorted({Path(z).name for z, _ in members.values()}),
        "index_mapping": "global",
        "verification": {"own_qa_agreement": round(own, 4),
                         "neighbour_qa_agreement": round(neighbour, 4)},
        "max_doc_chars": max_doc_chars,
        "n_claims": len(todo),
        "n_docs": total_docs,
        "n_gold": total_gold,
        "n_gold_empty_text": total_empty_gold,
        "claims_without_gold": no_gold,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    if limit:
        print(f"  --limit: left the smoke build at {partial}, not renamed into place")
        return 0
    if final.exists():
        shutil.rmtree(final)
    partial.replace(final)

    mins = (time.time() - started) / 60
    print(f"\n  {len(todo)} claims, {total_docs} docs, {total_gold} gold "
          f"({total_empty_gold} with no text), {mins:.1f} min")
    print(f"  docs/claim {total_docs / max(len(todo), 1):.0f}  "
          f"gold/claim {total_gold / max(len(todo), 1):.2f}")
    if no_gold:
        print(f"  WARNING: {len(no_gold)} claim(s) have no gold document and cannot "
              f"be scored for retrieval: {no_gold[:10]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/build_kb_cache.py")
    ap.add_argument("--split", default="dev", choices=["dev", "train"])
    ap.add_argument("--max-doc-chars", type=int, default=DEFAULT_MAX_DOC_CHARS)
    ap.add_argument("--limit", type=int, default=None,
                    help="first N claims only; a smoke build is never renamed into place")
    ap.add_argument("--force", action="store_true", help="rebuild an existing cache")
    args = ap.parse_args(argv)
    return build(args.split, args.max_doc_chars, args.limit, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
