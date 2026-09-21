"""Reader for the cached AVeriTeC knowledge store.

Evidence is per claim. AVeriTeC ships a candidate pool for each claim rather
than one global corpus, and retrieval is ranked **within that pool** — that is
AVeriTeC's own protocol and what keeps our Recall@k comparable with published
numbers. It is not a simplification.

Reads the compact cache written by `scripts/build_kb_cache.py`. Falls back to
the raw zip when no cache exists, so nothing is silently unrunnable, but the
cache is ~50x faster and is what every reported number should come from.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CACHE_ROOT = Path("data/interim")
ZIP_PATH = Path("data/raw/averitec_kb/dev_knowledge_store.zip")


@dataclass(frozen=True)
class Document:
    """One candidate document. `doc_id` is the URL, unique within a claim pool."""

    doc_id: str
    paragraphs: tuple[str, ...]
    is_gold: bool

    @property
    def text(self) -> str:
        return " ".join(self.paragraphs)


class KnowledgeStoreMissing(FileNotFoundError):
    pass


class KnowledgeStore:
    """Per-claim candidate pools for one AVeriTeC split."""

    def __init__(self, split: str = "dev", cache_root: Path | str = CACHE_ROOT):
        self.split = split
        self.cache_dir = Path(cache_root) / f"averitec_kb_{split}"
        self._zip: zipfile.ZipFile | None = None

    # -- discovery ------------------------------------------------------------
    @property
    def has_cache(self) -> bool:
        return self.cache_dir.is_dir() and any(self.cache_dir.glob("*.jsonl"))

    def available_claims(self) -> list[int]:
        if self.has_cache:
            return sorted(int(p.stem) for p in self.cache_dir.glob("*.jsonl")
                          if p.stem.isdigit())
        return sorted(self._zip_members())

    # -- loading --------------------------------------------------------------
    def pool(self, claim_idx: int) -> list[Document]:
        """Every candidate document for one claim."""
        if self.has_cache:
            path = self.cache_dir / f"{claim_idx}.jsonl"
            if not path.is_file():
                raise KnowledgeStoreMissing(
                    f"no cached pool for claim {claim_idx} at {path}. "
                    "Rebuild with `python scripts/build_kb_cache.py`."
                )
            with path.open("r", encoding="utf-8") as fh:
                return [
                    Document(r["doc_id"], tuple(r["paragraphs"]), bool(r["is_gold"]))
                    for r in map(json.loads, fh)
                ]
        return self._pool_from_zip(claim_idx)

    def gold_ids(self, claim_idx: int) -> list[str]:
        return [d.doc_id for d in self.pool(claim_idx) if d.is_gold]

    # -- zip fallback ---------------------------------------------------------
    def _members(self) -> dict[int, str]:
        return _zip_members_cached(str(ZIP_PATH))

    def _zip_members(self) -> dict[int, str]:
        return self._members()

    def _pool_from_zip(self, claim_idx: int) -> list[Document]:
        if not ZIP_PATH.is_file():
            raise KnowledgeStoreMissing(
                f"neither a cache at {self.cache_dir} nor the archive at {ZIP_PATH}. "
                "Run `make kb` then `python scripts/build_kb_cache.py`."
            )
        if self._zip is None:
            self._zip = zipfile.ZipFile(ZIP_PATH)
        member = self._members().get(claim_idx)
        if member is None:
            raise KnowledgeStoreMissing(f"claim {claim_idx} is not in {ZIP_PATH}")

        docs: dict[str, dict] = {}
        with self._zip.open(member) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                url = r.get("url")
                if not url:
                    continue
                entry = docs.setdefault(
                    url, {"paragraphs": r.get("url2text") or [], "is_gold": False}
                )
                if r.get("type") == "gold":
                    entry["is_gold"] = True
        return [Document(u, tuple(v["paragraphs"]), v["is_gold"]) for u, v in docs.items()]


@lru_cache(maxsize=2)
def _zip_members_cached(zip_path: str) -> dict[int, str]:
    with zipfile.ZipFile(zip_path) as z:
        out: dict[int, str] = {}
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            stem = name.rsplit("/", 1)[-1].removesuffix(".json")
            if stem.isdigit():
                out[int(stem)] = name
        return out


def claim_index_from_uid(source_id: str) -> int:
    """`averitec:dev.json:133` -> 133.

    The join between a frozen split row and its evidence pool. Verified in
    Phase 0: all 500 ids present, and each file's internal `claim_id` agrees
    with its filename.
    """
    try:
        return int(source_id.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        raise ValueError(
            f"cannot read a claim index from source_id {source_id!r}; "
            "expected something like 'averitec:dev.json:133'"
        ) from None
