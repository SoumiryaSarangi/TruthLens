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
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CACHE_ROOT = Path("data/interim")
KB_RAW = Path("data/raw/averitec_kb")

# Which archives hold which split, and the claim-index range each one covers.
# The single source of truth: the cache builder and the zip fallback below both
# read this, where each used to hard-code the DEV zip -- so `--split train` would
# have read the dev archive and written it into the train cache, silently.
#
# Member naming, MEASURED on the downloaded archives (2026-10-01) rather than
# inferred from the file names: every zip names its members by GLOBAL claim index
# (0-999, 1000-1999, 2000-3067 -- all 3,068 train.json claims), and each member's
# internal `claim_id` agrees. The directory prefixes differ by zip (`output_dev/`,
# none, `data_store/train/`), so members are matched on the basename.
KB_ZIPS: dict[str, tuple[tuple[str, int, int], ...]] = {
    "dev": (("dev_knowledge_store.zip", 0, 499),),
    "train": (("train_0_999.zip", 0, 999),
              ("train_1000_1999.zip", 1000, 1999),
              ("train_2000_3067.zip", 2000, 3067)),
}

# `<dataset>:<file>.json:<index>`. Strict about the part that matters: the file
# name is what says which knowledge store a row's evidence lives in, and a loose
# parser that kept only the integer is how a TEST claim ended up reading a DEV
# claim's pool. The dataset prefix is free (test fixtures use `toy:`); anything
# after the index -- a derived pair id like `...:2557:q0:a1` -- is refused.
_SOURCE_ID = re.compile(r"^[a-z0-9_]+:(train|dev)\.json:(\d+)$")


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

    def __init__(self, split: str = "dev", cache_root: Path | str = CACHE_ROOT,
                 raw_root: Path | str = KB_RAW):
        self.split = split
        self.cache_dir = Path(cache_root) / f"averitec_kb_{split}"
        self.raw_root = Path(raw_root)
        self._zips: dict[str, zipfile.ZipFile] = {}

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
    def _members(self) -> dict[int, tuple[str, str]]:
        return resolve_members(self.split, str(self.raw_root))

    def _zip_members(self) -> dict[int, tuple[str, str]]:
        return self._members()

    def _pool_from_zip(self, claim_idx: int) -> list[Document]:
        try:
            members = self._members()
        except KnowledgeStoreMissing as exc:
            raise KnowledgeStoreMissing(
                f"neither a cache at {self.cache_dir} nor a complete archive. {exc}"
            ) from None
        found = members.get(claim_idx)
        if found is None:
            raise KnowledgeStoreMissing(
                f"claim {claim_idx} is not in the {self.split} knowledge store")
        zip_path, member = found
        if zip_path not in self._zips:
            self._zips[zip_path] = zipfile.ZipFile(zip_path)

        docs: dict[str, dict] = {}
        with self._zips[zip_path].open(member) as fh:
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


def split_zips(split: str, raw_root: Path | str = KB_RAW) -> list[tuple[Path, int, int]]:
    """The archives for one split, with the claim-index range each covers.

    Never falls back to another split's archive. `test` is refused outright: its
    claims have no public labels, so nothing from it can be scored, and this
    project's test split is held out of train.json and lives in the TRAIN store.
    """
    if split not in KB_ZIPS:
        raise ValueError(
            f"no AVeriTeC knowledge store is used for split {split!r}; expected one "
            f"of {sorted(KB_ZIPS)}. The local test split's evidence is in 'train'."
        )
    root = Path(raw_root)
    out, missing = [], []
    for name, lo, hi in KB_ZIPS[split]:
        path = root / name
        if path.is_file():
            out.append((path, lo, hi))
        elif (root / f"{name}.part").is_file():
            missing.append(f"{name} (download incomplete -- rerun the downloader)")
        else:
            missing.append(name)
    if missing:
        raise KnowledgeStoreMissing(
            f"the {split} knowledge store is incomplete under {root}: missing "
            f"{', '.join(missing)}. Run `python scripts/download_knowledge_store.py "
            f"--split {split}`."
        )
    return out


def member_index(name: str) -> int | None:
    """Claim index from a zip member name, whatever directory prefix it carries."""
    base = name.rsplit("/", 1)[-1]
    if not base.endswith(".json"):
        return None
    stem = base.removesuffix(".json")
    return int(stem) if stem.isdigit() else None


@lru_cache(maxsize=4)
def resolve_members(split: str, raw_root: str = str(KB_RAW)) -> dict[int, tuple[str, str]]:
    """claim index -> (zip path, member name), across every archive of a split.

    Detects the naming rather than assuming it, per zip: members named inside
    [lo, hi] are GLOBAL indices; members inside [0, hi - lo] are OFFSETS from lo.
    Anything else, or two archives claiming one index, is refused -- a wrong
    mapping would hand a claim another claim's evidence and raise nothing.
    """
    out: dict[int, tuple[str, str]] = {}
    for path, lo, hi in split_zips(split, raw_root):
        with zipfile.ZipFile(path) as z:
            named = {idx: n for n in z.namelist() if (idx := member_index(n)) is not None}
        if not named:
            raise KnowledgeStoreMissing(f"{path.name} has no numbered .json members")
        if all(lo <= i <= hi for i in named):
            offset = 0
        elif lo and all(0 <= i <= hi - lo for i in named):
            offset = lo
        else:
            raise ValueError(
                f"{path.name}: member indices {min(named)}..{max(named)} fit neither "
                f"the global range {lo}..{hi} nor an offset from {lo}. Refusing "
                "rather than guessing which claim each file belongs to."
            )
        for idx, member in named.items():
            claim = idx + offset
            if claim in out:
                raise ValueError(f"claim {claim} appears in two archives: "
                                 f"{Path(out[claim][0]).name} and {path.name}")
            out[claim] = (str(path), member)
    return out


def kb_split_from_source_id(source_id: str) -> str:
    """`averitec:train.json:2557` -> `train`: which knowledge store holds the pool.

    This, not the split a row sits in, decides where its evidence lives. The
    local test split is 307 claims held out of the public train.json, so a TEST
    row's pool is in the TRAIN store.
    """
    match = _SOURCE_ID.match(source_id)
    if not match:
        raise ValueError(
            f"cannot read a claim index from source_id {source_id!r}; "
            "expected something like 'averitec:dev.json:133'"
        )
    return match.group(1)


def claim_index_from_uid(source_id: str) -> int:
    """`averitec:dev.json:133` -> 133.

    The join between a frozen split row and its evidence pool -- and only HALF of
    it. The index alone does not say which store it indexes into:
    `averitec:train.json:133` and `averitec:dev.json:133` are different claims.
    Pair this with `kb_split_from_source_id`, never use it on its own.
    """
    kb_split_from_source_id(source_id)          # validates the whole shape
    return int(source_id.rsplit(":", 1)[1])
