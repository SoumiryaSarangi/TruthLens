"""Which knowledge store a claim's evidence lives in, and building one safely.

Everything here uses synthetic archives in tmp_path, so it runs in CI with no
data. The failures worth pinning are the silent ones:

* A loose parser kept only the integer from `averitec:train.json:133`, and the
  batch runner looked it up in the DEV store. The local TEST split is 307 claims
  held out of train.json, so a test claim read an unrelated dev claim's pool --
  no error, and the final reported number would have been wrong.
* The cache builder hard-coded the dev archive, so `--split train` would have
  written the dev store into the train cache.
* An interrupted build or a truncated download must never pass for complete.
"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

from common.io_jsonl import write_json
from retrieval import kb
from retrieval.kb import (
    KB_ZIPS,
    KnowledgeStore,
    KnowledgeStoreMissing,
    claim_index_from_uid,
    kb_split_from_source_id,
    member_index,
    resolve_members,
    split_zips,
)

ROOT = Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _zip(path: Path, members: dict[str, list[dict]]) -> Path:
    """An archive in AVeriTeC's shape: one JSON-lines member per claim."""
    with zipfile.ZipFile(path, "w") as z:
        for name, rows in members.items():
            z.writestr(name, "\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def _rows(claim: int, gold_url: str) -> list[dict]:
    return [
        {"claim_id": str(claim), "type": "gold", "url": gold_url,
         "url2text": [f"evidence for claim {claim}"]},
        {"claim_id": str(claim), "type": "search", "url": f"https://x.example/{claim}",
         "url2text": ["unrelated page"]},
    ]


@pytest.fixture(autouse=True)
def _fresh_member_cache():
    resolve_members.cache_clear()
    yield
    resolve_members.cache_clear()


@pytest.fixture
def train_store(tmp_path, monkeypatch):
    """A three-archive train store, global member names, like the real one."""
    monkeypatch.setitem(KB_ZIPS, "train", (("t0.zip", 0, 1), ("t1.zip", 2, 3),
                                           ("t2.zip", 4, 5)))
    _zip(tmp_path / "t0.zip", {"0.json": _rows(0, "https://g/0"),
                               "1.json": _rows(1, "https://g/1")})
    _zip(tmp_path / "t1.zip", {"2.json": _rows(2, "https://g/2"),
                               "3.json": _rows(3, "https://g/3")})
    _zip(tmp_path / "t2.zip", {"data_store/train/4.json": _rows(4, "https://g/4"),
                               "data_store/train/5.json": _rows(5, "https://g/5")})
    return tmp_path


# -----------------------------------------------------------------------------
# Which store holds a row's evidence
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("source_id, store, index", [
    ("averitec:dev.json:133", "dev", 133),
    ("averitec:train.json:133", "train", 133),
    ("averitec:train.json:2557", "train", 2557),
])
def test_the_file_in_the_source_id_decides_the_store(source_id, store, index):
    """`train.json:133` and `dev.json:133` are DIFFERENT claims. The index alone
    does not say which pool it indexes into."""
    assert kb_split_from_source_id(source_id) == store
    assert claim_index_from_uid(source_id) == index


@pytest.mark.parametrize("bad", [
    "averitec:test.json:5",             # no public test labels; nothing to score
    "averitec_stance:train.json:5:q0:a1",
    "133",
    "averitec:dev.json:",
])
def test_a_source_id_that_names_no_store_is_refused(bad):
    with pytest.raises(ValueError):
        kb_split_from_source_id(bad)


def test_a_test_split_row_resolves_to_the_train_store():
    """The bug this file exists for. All 307 local test claims come from
    train.json, so their evidence is in the TRAIN store."""
    from pipeline.batch import evidence_store_for

    rows = [{"source_id": "averitec:train.json:12"},
            {"source_id": "averitec:train.json:2557"}]
    assert evidence_store_for(rows, Path("data/splits/averitec/test.jsonl")) == "train"


def test_a_run_mixing_two_stores_is_refused():
    from pipeline.batch import evidence_store_for

    rows = [{"source_id": "averitec:train.json:12"},
            {"source_id": "averitec:dev.json:12"}]
    with pytest.raises(SystemExit, match="mixes"):
        evidence_store_for(rows, Path("x.jsonl"))


# -----------------------------------------------------------------------------
# Resolving archives
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("name, index", [
    ("0.json", 0), ("output_dev/133.json", 133), ("data_store/train/2495.json", 2495),
    ("output_dev/", None), ("README.md", None), ("abc.json", None),
])
def test_member_names_resolve_whatever_their_directory_prefix(name, index):
    """Measured on the real archives: `output_dev/`, no prefix, and
    `data_store/train/` all occur."""
    assert member_index(name) == index


def test_global_member_names_map_to_themselves(train_store):
    members = resolve_members("train", str(train_store))
    assert sorted(members) == [0, 1, 2, 3, 4, 5]
    assert Path(members[4][0]).name == "t2.zip"


def test_offset_member_names_shift_by_the_archive_base(tmp_path, monkeypatch):
    """A zip naming its members 0..1 while covering claims 2..3 is offset-named."""
    monkeypatch.setitem(KB_ZIPS, "train", (("t0.zip", 0, 1), ("t1.zip", 2, 3)))
    _zip(tmp_path / "t0.zip", {"0.json": _rows(0, "a"), "1.json": _rows(1, "b")})
    _zip(tmp_path / "t1.zip", {"0.json": _rows(2, "c"), "1.json": _rows(3, "d")})
    members = resolve_members("train", str(tmp_path))
    assert members[2] == (str(tmp_path / "t1.zip"), "0.json")


def test_names_fitting_neither_range_are_refused(tmp_path, monkeypatch):
    monkeypatch.setitem(KB_ZIPS, "train", (("t1.zip", 10, 11),))
    _zip(tmp_path / "t1.zip", {"500.json": _rows(500, "a")})
    with pytest.raises(ValueError, match="neither"):
        resolve_members("train", str(tmp_path))


def test_a_missing_archive_is_refused_and_never_replaced_by_dev(tmp_path, monkeypatch):
    """The old code hard-coded the DEV zip; a train lookup must not reach it."""
    monkeypatch.setitem(KB_ZIPS, "train", (("t0.zip", 0, 1),))
    _zip(tmp_path / "dev_knowledge_store.zip", {"0.json": _rows(0, "dev")})
    with pytest.raises(KnowledgeStoreMissing, match=r"t0.zip"):
        split_zips("train", tmp_path)


def test_a_part_file_is_reported_as_an_incomplete_download(tmp_path, monkeypatch):
    monkeypatch.setitem(KB_ZIPS, "train", (("t0.zip", 0, 1),))
    (tmp_path / "t0.zip.part").write_bytes(b"half a download")
    with pytest.raises(KnowledgeStoreMissing, match="incomplete"):
        split_zips("train", tmp_path)


def test_the_test_split_has_no_store_to_read():
    """Its labels are not public, so nothing downloaded from it could be scored."""
    with pytest.raises(ValueError, match="train"):
        split_zips("test")


def test_the_zip_fallback_reads_the_right_archive(train_store, tmp_path):
    store = KnowledgeStore("train", cache_root=tmp_path / "no-cache",
                           raw_root=train_store)
    assert store.gold_ids(4) == ["https://g/4"]
    assert store.gold_ids(1) == ["https://g/1"]


def test_the_downloader_and_the_reader_agree_on_the_archive_names():
    """Two lists of the same files are two places to forget one."""
    downloader = _script("download_knowledge_store")
    for split in ("dev", "train"):
        assert ({Path(p).name for p in downloader.SPLITS[split]}
                == {name for name, _, _ in kb.KB_ZIPS[split]})


# -----------------------------------------------------------------------------
# Building a cache
# -----------------------------------------------------------------------------


@pytest.fixture
def builder(train_store, tmp_path, monkeypatch):
    """The cache builder pointed at the synthetic store and a synthetic train.json."""
    module = _script("build_kb_cache")
    out = tmp_path / "interim"
    raw_averitec = tmp_path / "averitec"
    raw_averitec.mkdir()
    claims = [{"questions": [{"answers": [{"source_url": f"https://g/{i}"}]}]}
              for i in range(6)]
    (raw_averitec / "train.json").write_text(json.dumps(claims), encoding="utf-8")
    write_json(train_store / "DOWNLOADS.json", {
        name: {"bytes": (train_store / name).stat().st_size}
        for name in ("t0.zip", "t1.zip", "t2.zip")})
    monkeypatch.setattr(module, "OUT_ROOT", out)
    monkeypatch.setattr(module, "RAW_AVERITEC", raw_averitec)
    monkeypatch.setattr(module, "KB_RAW", train_store)
    monkeypatch.setattr(module, "split_zips",
                        lambda split, raw=train_store: split_zips(split, train_store))
    monkeypatch.setattr(module, "resolve_members",
                        lambda split: resolve_members(split, str(train_store)))
    return module, out


def test_a_complete_build_lands_in_place_with_a_verified_manifest(builder):
    module, out = builder
    assert module.build("train", max_doc_chars=4000) == 0
    manifest = json.loads((out / "averitec_kb_train" / "MANIFEST.json").read_text())
    assert manifest["n_claims"] == 6
    assert manifest["verification"]["own_qa_agreement"] == 1.0
    assert not (out / "averitec_kb_train.partial").exists()


def test_an_archive_missing_from_the_download_manifest_is_refused(builder, train_store):
    module, _ = builder
    write_json(train_store / "DOWNLOADS.json", {"t0.zip": {"bytes": 1}})
    assert module.build("train", max_doc_chars=4000) == 2


def test_a_size_disagreeing_with_the_manifest_is_refused(builder, train_store):
    """A truncated download has the right name and the wrong size."""
    module, _ = builder
    manifest = json.loads((train_store / "DOWNLOADS.json").read_text())
    manifest["t1.zip"]["bytes"] += 1
    write_json(train_store / "DOWNLOADS.json", manifest)
    assert module.build("train", max_doc_chars=4000) == 2


def test_a_claim_id_disagreeing_with_its_file_is_refused(builder, train_store):
    """claim_id is a STRING in the real archives; the check must compare as one."""
    module, out = builder
    _zip(train_store / "t1.zip", {"2.json": _rows(99, "https://g/2"),
                                  "3.json": _rows(3, "https://g/3")})
    manifest = json.loads((train_store / "DOWNLOADS.json").read_text())
    manifest["t1.zip"]["bytes"] = (train_store / "t1.zip").stat().st_size
    write_json(train_store / "DOWNLOADS.json", manifest)
    resolve_members.cache_clear()
    assert module.build("train", max_doc_chars=4000) == 2
    assert not (out / "averitec_kb_train").exists(), "a refused build must not land"


def test_a_shifted_mapping_fails_the_own_qa_check(builder, tmp_path):
    """Every claim's gold points at its NEIGHBOUR's sources: an off-by-one filing
    that the claim_id check alone could miss."""
    module, out = builder
    claims = [{"questions": [{"answers": [{"source_url": f"https://g/{i + 1}"}]}]}
              for i in range(6)]
    (tmp_path / "averitec" / "train.json").write_text(json.dumps(claims),
                                                       encoding="utf-8")
    assert module.build("train", max_doc_chars=4000) == 2
    assert not (out / "averitec_kb_train").exists()


def test_a_smoke_build_is_never_renamed_into_place(builder):
    """--limit would otherwise publish a store with most of its claims missing."""
    module, out = builder
    assert module.build("train", max_doc_chars=4000, limit=2) == 0
    assert not (out / "averitec_kb_train").exists()
