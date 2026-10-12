"""Start the demo server in any shell (PowerShell, cmd, bash).

    .venv\Scripts\python.exe scripts\serve.py        (Windows)
    make serve                                          (same thing, Git Bash / Linux)

`make serve` used to set the warm-up variable with Unix syntax, which PowerShell
and cmd reject. Warm-up loads every model before the first request, so the first
click does not wait 30+ s.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("TRUTHLENS_WARMUP", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if __name__ == "__main__":
    import uvicorn

    # Local by default. A deployment sets TRUTHLENS_HOST (0.0.0.0 inside a container or behind a reverse proxy on the same machine
    # should still use 127.0.0.1 and let the proxy face the network) and PORT. There is no authentication: see SECURITY.md.
    host = os.environ.get("TRUTHLENS_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port)
