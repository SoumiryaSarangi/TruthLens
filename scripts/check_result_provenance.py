"""Which results still reproduce from their recorded inputs (Phase 7).

    python scripts/check_result_provenance.py            # report only
    python scripts/check_result_provenance.py --rescore  # re-score what reproduces

A result marked `git.dirty` was scored while the working tree had uncommitted
changes -- usually its own config, untracked at the time. The number may well be
right; the flag says the committed code was not proven to produce it.

A result is re-scored only if re-scoring would reproduce the SAME run: the
predictions file still hashes to the recorded sha256, the split lock is the one
it was scored under, and today's config resolves to the same config_hash. Then
`make eval` from a clean tree overwrites results/<hash>.json with dirty=false.
Anything else is reported and left alone -- a re-score under a different hash
would be a new run wearing an old run's name, and other configs chain to these
hashes as baselines.

This reads files and recomputes hashes; it computes no metric.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.hashing import canonical_json, sha256_bytes, sha256_file  # noqa: E402
from common.io_jsonl import load_json  # noqa: E402
from common.provenance import git_info  # noqa: E402
from eval.evaluate import CONFIG_HASH_LEN, find_lock_for, load_config  # noqa: E402

RESULTS = Path("results")


def status(doc: dict) -> str:
    """Why this run would or would not reproduce, as one word."""
    inputs = doc["inputs"]
    pred = Path(inputs["predictions_path"])
    if not pred.is_file():
        return "predictions-missing"
    pred_sha = sha256_file(pred)
    if pred_sha != inputs["predictions_sha256"]:
        return "predictions-changed"
    config_path = Path(inputs.get("config_path") or "")
    if not config_path.is_file():
        return "config-missing"
    split = Path(inputs["split_path"])
    if not split.is_file() or sha256_file(split) != inputs.get("split_sha256"):
        return "split-changed"
    lock = find_lock_for(split)
    lock_sha = sha256_file(lock) if lock else None
    if lock_sha != inputs.get("splits_lock_sha256"):
        # The lock covers every split, so it moves whenever one is ADDED. This
        # run's own split and predictions are byte-identical; only a re-score
        # under the same hash is impossible.
        return "inputs-same-lock-grew"
    try:
        cfg = load_config(config_path)
    except Exception:          # any failure to load is "does not reproduce"
        return "config-invalid"
    would_be = sha256_bytes(canonical_json(cfg) + pred_sha.encode()
                            + (lock_sha or "nolock").encode())[:CONFIG_HASH_LEN]
    return "reproduces" if would_be == doc["config_hash"] else "config-changed"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python scripts/check_result_provenance.py")
    ap.add_argument("--rescore", action="store_true",
                    help="re-score each dirty result that reproduces (clean tree only)")
    ap.add_argument("--all", action="store_true",
                    help="check every result, not only the dirty ones")
    args = ap.parse_args(argv)

    rows = []
    for path in sorted(RESULTS.glob("*.json")):
        doc = load_json(path)
        if "inputs" not in doc or not (args.all or doc.get("git", {}).get("dirty")):
            continue
        rows.append((doc, status(doc)))

    # Baselines first: a run that pairs against a prior hash needs that prior
    # on disk before it is re-scored.
    rows.sort(key=lambda r: (len(str(r[0]["inputs"]["config"].get("baseline", ""))) ==
                             CONFIG_HASH_LEN, r[0]["experiment"]))
    for doc, why in rows:
        print(f"{doc['config_hash']}  {why:<20} {doc['experiment']}")
    print(dict(Counter(why for _, why in rows)))

    if not args.rescore:
        return 0
    if git_info().get("dirty"):
        print("REFUSED: the tree is dirty; a re-score would be dirty too. Commit first.")
        return 2
    for doc, why in rows:
        if why != "reproduces":
            continue
        cfg = doc["inputs"]["config_path"]
        print(f"re-scoring {doc['config_hash']} {cfg}", flush=True)
        done = subprocess.run([sys.executable, "-m", "eval.evaluate", "--config", cfg],
                              cwd=ROOT, check=False, capture_output=True, text=True,
                              encoding="utf-8",
                              env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                   "PYTHONPATH": str(ROOT / "src")})
        if done.returncode != 0:
            print(done.stdout[-1500:], done.stderr[-1500:])
            return done.returncode
        after = load_json(RESULTS / f"{doc['config_hash']}.json")
        if after.get("git", {}).get("dirty"):
            print(f"  still dirty: {doc['config_hash']}")
            return 1
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
