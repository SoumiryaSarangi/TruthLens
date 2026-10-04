"""Does the SHIPPED live verdict reproduce what protocol 2 MEASURED?

    python scripts/live_ship_check.py --n 150

Runs stored FEVER-fresh claims through the real `Orchestrator.verify(claim, live=True)` with
the served config (dev.yaml: live_verdict and live_translate on, the two-model rule inside
the orchestrator) and compares each card with the V2 prediction that `scripts/live_fever.py`
computed OFFLINE from stored probabilities and that the pre-registered gates were read from.
Wikipedia and Google responses come from the disk cache of the measurement run, so this
costs no network; a claim whose cache entry is missing is reported, not guessed.

Also reports the peak GPU memory and the per-claim time with every live model loaded.
This prints a comparison; it computes no metric.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="English claims to compare")
    ap.add_argument("--sub", type=int, default=20, help="claims from each of the hi and pa subsets")
    args = ap.parse_args()

    import torch

    import live_fever as L
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    cfg = PipelineConfig.load(ROOT / "configs/pipeline/dev.yaml")
    cfg.stages["generation"] = "template"          # the verdict does not depend on the explainer
    orch = Orchestrator(cfg)
    orch.verify("warm-up")
    t0 = time.perf_counter()
    orch.warm_live()
    print(f"live models loaded in {time.perf_counter() - t0:.1f} s", flush=True)

    batches = [("en", L.read_jsonl(L.OUT / "fresh_en.scored.jsonl")[:args.n])]
    for lang in ("hi", "pa"):
        batches.append((lang, L.read_jsonl(L.OUT / f"fresh_sub_{lang}.scored.jsonl")[:args.sub]))
    seen = same = 0
    diffs, times = [], []
    for lang, rows in batches:
        for rec in rows:
            if rec["n_results"] != 1:              # a multi-claim post: the harness used the card
                continue
            want = L.variant_predictions(rec)["v2"][0]
            t1 = time.perf_counter()
            trace = orch.verify(rec["text"], live=True)
            times.append(time.perf_counter() - t1)
            got, _ = L.shown(trace.results[0] if trace.results else None)
            seen += 1
            same += got == want
            if got != want:
                diffs.append((lang, rec["uid"], want, got, [e.note for e in trace.events
                                                            if e.note and "degraded" in e.note]))
    print(f"compared {seen} cards: {same} identical, {len(diffs)} different")
    for d in diffs:
        print("  DIFF", d)
    if times:
        print(f"median {statistics.median(times):.2f} s, p95 {sorted(times)[int(0.95 * len(times)) - 1]:.2f} s per live click")
    if torch.cuda.is_available():
        print(f"peak GPU memory allocated: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB "
              f"of {torch.cuda.get_device_properties(0).total_memory / 2**30:.2f} GiB")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
