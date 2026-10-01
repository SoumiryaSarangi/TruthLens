"""Explanation training and oracle data from AVeriTeC (Phase 6, FR-15).

One place builds (claim, verdict, gold QA evidence, cleaned justification) per
claim, so the trainer, the oracle evaluation and the reference file for chrF all
read the same thing. Split membership comes from the frozen split files, never
from iterating train.json -- the local test split is held out of train.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from common.io_jsonl import load_jsonl
from data.labels import map_averitec_label
from data.loaders import averitec_evidence
from generation.indicbart import clean_justification
from retrieval.kb import claim_index_from_uid

RAW = Path("data/raw/averitec")
MAX_QA = 6


def gold_evidence(record: dict) -> list[str]:
    """One passage per QA answer, formatted as the stance gold is."""
    out = []
    for q in record.get("questions") or []:
        for a in q.get("answers") or []:
            text = averitec_evidence(q, a)
            if text:
                out.append(text)
    return out[:MAX_QA]


def examples(split: str) -> list[dict]:
    """(claim, verdict, gold evidence, cleaned justification) for one split."""
    raw: dict[str, list] = {}
    rows = []
    for row in load_jsonl(Path("data/splits/averitec") / f"{split}.jsonl"):
        file = row["source_id"].split(":")[1]
        if file not in raw:
            raw[file] = json.loads((RAW / file).read_text(encoding="utf-8"))
        rec = raw[file][claim_index_from_uid(row["source_id"])]
        target = clean_justification(rec.get("justification") or "")
        if not target:
            continue
        rows.append({"uid": row["uid"], "claim": rec["claim"],
                     "verdict": map_averitec_label(rec["label"]),
                     "evidence": gold_evidence(rec), "target": target})
    return rows
