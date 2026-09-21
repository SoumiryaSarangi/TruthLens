"""FastAPI app. SYSTEM_DESIGN.md §8.

Serves the **same orchestrator** the batch runner evaluates (§1). There is no
separate demo path that could drift from the one the numbers came from.

Phase 1 caveat, surfaced rather than hidden: retrieval is per AVeriTeC claim
pool, so free-text input has nothing to search until the demo corpus exists
(§7). Such a request gets NEI with `abstained=true` and a trace note saying
why, instead of a fabricated verdict. `?claim_idx=` runs a real dev claim end
to end, which is what the demo shows.
"""

from __future__ import annotations

import os
import subprocess
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
# Phase 1 values are placeholders -- the real cut points come off the
# calibration curve in Phase 6, which is why they are here and not in app.js.
CONFIDENCE_BANDS = {"high": 0.75, "medium": 0.5}

app = FastAPI(title="TruthLens", version="0.1.0")

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


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.post("/verify")
def verify(req: VerifyRequest, claim_idx: int | None = Query(default=None)) -> dict[str, Any]:
    if not req.text.strip():
        # FR-1: whitespace-only is a validation error, never a verdict.
        raise HTTPException(status_code=422, detail="Message is empty")

    orch = get_orchestrator()
    trace = orch.verify(req.text, claim_idx=claim_idx)

    pre = trace.pre
    body: dict[str, Any] = {
        "request_id": trace.request_id,
        "input": {
            "original": pre.original if pre else req.text,
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
