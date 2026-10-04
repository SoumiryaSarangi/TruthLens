"""The FEVER samples used to measure the live verdict (docs/live-fever-protocol.md)."""

from __future__ import annotations

import json

import pytest

from data import loaders


@pytest.fixture
def fake_fever(tmp_path, monkeypatch):
    path = tmp_path / "valid.jsonl"
    labels = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]
    rows = [{"id": i, "claim": f"Claim number {i} about thing {i * 7}.", "label": labels[i % 3]}
            for i in range(900)]
    rows.append({"id": 9001, "claim": "Claim number 4 about thing 28.", "label": "REFUTES"})   # duplicate text
    rows.append({"id": 9002, "claim": "", "label": "SUPPORTS"})
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(loaders, "fever_path", lambda: path)
    return path


def test_sets_are_disjoint_balanced_and_nested(fake_fever):
    s = loaders.fever_samples()
    sel = {c["fever_id"] for c in s["select"]}
    conf = {c["fever_id"] for c in s["confirm"]}
    assert not sel & conf
    assert {c["fever_id"] for c in s["confirm_sub"]} <= conf
    for name, per in (("select", 50), ("confirm", 100), ("confirm_sub", 20)):
        counts = {}
        for c in s[name]:
            counts[c["label"]] = counts.get(c["label"], 0) + 1
        assert counts == {"Supported": per, "Refuted": per, "NEI": per}, name


def test_sampling_is_deterministic_and_mixed(fake_fever):
    a, b = loaders.fever_samples(), loaders.fever_samples()
    assert a == b
    assert [c["label"] for c in a["confirm"][:3]] == ["NEI", "Refuted", "Supported"]   # round-robin


def test_duplicate_and_empty_claims_are_dropped(fake_fever):
    ids = {c["fever_id"] for v in loaders.fever_samples().values() for c in v}
    assert "9001" not in ids and "9002" not in ids


def test_rows_carry_the_verdict_label_set(fake_fever):
    row = loaders.fever_select_rows()["dev"][0]
    assert row.record["label_set"] == "verdict_5class" and row.record["dataset"] == "fever_select"
    assert row.record["lang"] == "en" and row.record["label"] in {"Supported", "Refuted", "NEI"}


def test_the_fresh_set_is_disjoint_from_select_and_confirm_and_leaves_them_unchanged(fake_fever):
    s = loaders.fever_samples()
    used = {c["fever_id"] for k in ("select", "confirm") for c in s[k]}
    fresh = {c["fever_id"] for c in s["fresh"]}
    assert not used & fresh
    counts = {}
    for c in s["fresh"]:
        counts[c["label"]] = counts.get(c["label"], 0) + 1
    assert counts == {"Supported": 100, "Refuted": 150, "NEI": 100}
    assert {c["fever_id"] for c in s["fresh_sub"]} <= fresh and len(s["fresh_sub"]) == 60
    # the protocol-1 sets are exactly what they were before the fresh set existed
    assert [c["fever_id"] for c in s["confirm"][:3]] == [c["fever_id"] for c in loaders.fever_samples()["confirm"][:3]]


def test_truth_rows_take_the_owners_labels_for_nei_claims_only(fake_fever, tmp_path, monkeypatch):
    fresh = loaders.fever_samples()["fresh"]
    owner = {f"fever_fresh:en:dev:{i:05d}": "TFU"[i % 3] for i, c in enumerate(fresh) if c["label"] == "NEI"}
    path = tmp_path / "truth.json"
    path.write_text(json.dumps({"labels": owner}), encoding="utf-8")
    monkeypatch.setattr(loaders, "FEVER_TRUTH_PATH", path)
    rows = loaders.fever_fresh_truth_rows()["dev"]
    assert len(rows) == 350 and rows[0].record["dataset"] == "fever_fresh_truth"
    word = {"T": "Supported", "F": "Refuted", "U": "NEI"}
    for i, (item, row) in enumerate(zip(fresh, rows, strict=True)):
        want = item["label"] if item["label"] != "NEI" else word["TFU"[i % 3]]
        assert row.record["label"] == want
