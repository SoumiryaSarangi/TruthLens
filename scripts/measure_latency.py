"""NFR-1, NFR-2, NFR-3 on the served pipeline, measured the way a user meets it.

    python scripts/measure_latency.py            # writes reports/latency.json

- **Cold start (NFR-2, <= 90 s)**: from this process starting to the first
  answer of a forward that loads every model -- what `make serve` does before
  it reports ready.
- **Warm latency (NFR-1)**: p50 / p95 per request, split by the path the
  request took, because the budgets differ -- evidence path <= 10 s, fast path
  <= 3 s. Inputs: the demo chips and regression forwards, 40 AVeriTeC dev claims
  as free text (seed 42), and up to 20 MultiClaim dev posts the fast path
  answers -- so the fast-path percentile rests on more than one chip.
- **Peak VRAM (NFR-3, <= 5.5 GB)**: torch's max_memory_allocated over the run.

In-process, through `Orchestrator.verify` -- the code `POST /verify` calls -- so
HTTP overhead (~ms on localhost) is not counted. These are measurements of the
system, not model metrics; nothing here is scored.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

STARTED = time.perf_counter()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "reports" / "latency.json"
COLD_INPUT = "Sarkar ne announce kiya hai ki har student ko 6000 rupaye milenge"


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: the smallest value with >= q of the data at or below it."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = max(1, -(-int(q * 100) * len(ordered) // 100))     # ceil(q * n)
    return ordered[min(rank, len(ordered)) - 1]


def inputs() -> list[str]:
    from common.io_jsonl import load_jsonl

    samples = json.loads((ROOT / "app/static/samples.json").read_text(encoding="utf-8"))
    texts = [c["text"] for c in samples["chips"]] + [r["text"] for r in samples["regression"]]
    claims = [r["text"] for r in load_jsonl(ROOT / "data/interim/averitec/dev.jsonl")]
    texts += random.Random(42).sample(claims, 40)
    # MultiClaim dev posts the BGE-M3 gate scores >= 0.90 (Phase 2 predictions):
    # stored scores, so this needs no model to choose them.
    preds = ROOT / "results/preds/p2_match_bge_m3.jsonl"
    posts = ROOT / "data/interim/multiclaim/dev.jsonl"
    if preds.is_file() and posts.is_file():
        text_of = {r["uid"]: r["text"] for r in load_jsonl(posts)}
        fast = [text_of[r["uid"]] for r in load_jsonl(preds)
                if r["scores"] and r["scores"][0] >= 0.90 and r["uid"] in text_of]
        texts += fast[:20]
    return texts


def main() -> int:
    from pipeline.orchestrator import Orchestrator, PipelineConfig

    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        torch, cuda = None, False

    orch = Orchestrator(PipelineConfig.load(ROOT / "configs/pipeline/dev.yaml"))
    orch.verify(COLD_INPUT)
    cold_s = time.perf_counter() - STARTED

    timings: dict[str, list[float]] = {"evidence": [], "fast": [], "none": []}
    for text in inputs():
        t0 = time.perf_counter()
        trace = orch.verify(text)
        ms = (time.perf_counter() - t0) * 1000
        path = trace.results[0].path if trace.results else "none"
        timings.setdefault(path, []).append(ms)

    def summary(values: list[float]) -> dict[str, float]:
        return {"n": len(values), "p50_s": round(percentile(values, 0.50) / 1000, 3),
                "p95_s": round(percentile(values, 0.95) / 1000, 3),
                "max_s": round(max(values) / 1000, 3) if values else float("nan")}

    every = [v for vs in timings.values() for v in vs]
    report = {
        "config": "configs/pipeline/dev.yaml",
        "cold_start_s": round(cold_s, 1),
        "warm": {"all": summary(every),
                 **{path: summary(vs) for path, vs in timings.items() if vs}},
        "peak_vram_gib": (round(torch.cuda.max_memory_allocated() / 2**30, 2)
                          if cuda else None),
        "device": torch.cuda.get_device_name(0) if cuda else "cpu",
        "budgets": {"NFR-1 evidence p95_s": 10, "NFR-1 fast p95_s": 3,
                    "NFR-2 cold_start_s": 90, "NFR-3 peak_vram_gib": 5.5 * 1e9 / 2**30},
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
