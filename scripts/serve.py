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

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
