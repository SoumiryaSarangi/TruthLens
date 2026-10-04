"""FastAPI app. SYSTEM_DESIGN.md §8.

Serves the **same orchestrator** the batch runner evaluates (§1). There is no
separate demo path that could drift from the one the numbers came from.

Free text is searched against the demo corpus (Phase 5, `free_text_retrieval`);
`?claim_idx=` runs a real AVeriTeC dev claim against its own evidence pool.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline.orchestrator import Orchestrator, PipelineConfig

STATIC = Path(__file__).parent / "static"
DEFAULT_CONFIG = Path("configs/pipeline/dev.yaml")

MAX_CHARS = 4000        # FR-1

# UI_UX.md §7: the confidence bands are served, never hard-coded in JavaScript.
# Cut points from the reliability bins of the SERVED arm on dev (run
# 164d2289c90b, temperature-scaled): `medium` is the bin edge where dev accuracy
# first reaches 0.5 (0.40-0.50: 0.52, n=148); `high` the edge of the
# best-supported bin near 0.75 (0.60-0.70: 0.74, n=35). Below tau_abstain
# (0.3835) the card is abstained, not "low". These move with the served arm.
CONFIDENCE_BANDS = {"high": 0.60, "medium": 0.40}

# A statement that runs every stage -- check-worthy, the demo corpus, stance,
# the aggregator, generation and the gate -- so the first real request is not
# the one that pays for loading five models. SYSTEM_DESIGN 13.
WARMUP_TEXT = "Delhi is the capital of India."


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Opt-in (`make serve` sets it), so the API tests do not load every model.
    if os.environ.get("TRUTHLENS_WARMUP") == "1":
        t0 = time.perf_counter()
        get_orchestrator().verify(WARMUP_TEXT)
        print(f"warm-up request done in {time.perf_counter() - t0:.1f} s", flush=True)

        def warm_live() -> None:
            t1 = time.perf_counter()
            get_orchestrator().warm_live()      # live-verdict models; no network
            print(f"live models loaded in {time.perf_counter() - t1:.1f} s", flush=True)

        # In the background: the server is ready once the offline stack is (NFR-2, 90 s);
        # a live click that arrives first waits for these models instead of failing.
        threading.Thread(target=warm_live, name="warm-live", daemon=True).start()
    yield


app = FastAPI(title="TruthLens", version="0.1.0", lifespan=lifespan)

_orchestrator: Orchestrator | None = None
_config: PipelineConfig | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator, _config
    if _orchestrator is None:
        _config = (PipelineConfig.load(DEFAULT_CONFIG) if DEFAULT_CONFIG.is_file()
                   else PipelineConfig())
        _orchestrator = Orchestrator(_config)
    return _orchestrator


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class VerifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    lang_hint: str | None = None
    include_trace: bool = True
    # Post-test Phase 7: send THIS text to Wikipedia and Google Fact Check. False
    # unless the user clicked "search live" -- explicit, per claim (SRS NFR-8).
    live_search: bool = False
    # "Check it anyway": the claim gate called a short fragment not a claim and the reader asked
    # for it to be checked as one. Off unless the reader clicked; never used in an evaluation.
    force_claim: bool = False


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.post("/verify")
def verify(req: VerifyRequest, claim_idx: int | None = Query(default=None)) -> dict[str, Any]:
    if not req.text.strip():
        # FR-1: whitespace-only is a validation error, never a verdict.
        raise HTTPException(status_code=422, detail="Message is empty")

    # Unicode NFC at the server's door. The same Punjabi or Hindi sentence typed or pasted with a
    # precomposed letter (ਫ਼ U+0A5E, क़ U+0958) or with a base letter plus a nukta (U+0A3C, U+093C) is the
    # same text to a reader but different characters to a model, and gave different verdicts
    # (Refuted against NEI on one chip sentence). Only this entry point does it, so the evaluation
    # runs, which never come through here, and every reported number are untouched.
    text = unicodedata.normalize("NFC", req.text)

    orch = get_orchestrator()
    trace = orch.verify(text, claim_idx=claim_idx, live=req.live_search, force_claim=req.force_claim)

    pre = trace.pre
    body: dict[str, Any] = {
        "request_id": trace.request_id,
        "input": {
            "original": pre.original if pre else text,
            "normalized": pre.normalized if pre else "",
            "lang": pre.lang if pre else "other",
            "script": pre.script if pre else "latn",
            "script_purity": pre.script_purity if pre else 0.0,
            "transliterated": pre.transliterated if pre else None,
        },
        "checkworthy": trace.checkworthy,
        "results": [r.model_dump() for r in trace.results],
        "unchecked_claims": trace.unchecked_claims,
    }
    if req.include_trace:
        body["trace"] = {"events": [e.model_dump() for e in trace.events]}
    return body


@app.get("/health")
def health() -> dict[str, Any]:
    orch = get_orchestrator()
    stages: dict[str, str] = {}
    for stage, obj in (("retrieval", orch.retriever), ("stance", orch.stance),
                       ("generation", orch.generator), ("matching", orch.matcher)):
        loaded = getattr(obj, "loaded", True)
        stages[stage] = f"{obj.impl}:{'loaded' if loaded else 'not_loaded'}"
    degraded = any(v.endswith("not_loaded") for v in stages.values())
    return {"status": "degraded" if degraded else "ok", "stages": stages}


@app.get("/version")
def version() -> dict[str, Any]:
    get_orchestrator()
    cfg = _config or PipelineConfig()
    return {
        "git_sha": _git_sha(),
        "pipeline_config": str(DEFAULT_CONFIG),
        "config": cfg.describe(),
        "tau_match": cfg.tau_match,
        "tau_abstain": cfg.tau_abstain,
        "confidence_bands": CONFIDENCE_BANDS,
    }


def _git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":       # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
