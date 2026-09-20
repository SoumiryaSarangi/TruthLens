"""Run provenance: what code, what interpreter, what packages produced a number.

Stamped into every results/{config_hash}.json. Without this a number from a
laptop CPU run and a number from a Colab GPU run look identical in the results
table, and the report compares two things that were never comparable.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

# Recorded if installed. torch is listed because the CPU vs CUDA build string is
# the single most useful thing to know when two runs disagree.
_TRACKED_PACKAGES = (
    "numpy", "pandas", "scikit-learn", "scipy", "pyyaml", "jsonschema",
    "datasketch", "torch", "transformers", "sentence-transformers",
    "faiss-cpu", "faiss-gpu", "rank-bm25",
)


def _git(*args: str, repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git_info(repo: str | Path | None = None) -> dict[str, object]:
    """Current commit and whether the tree was dirty when the run happened.

    `dirty: true` in a results file means the committed code does not reproduce
    that number. It is recorded rather than blocked, but it is recorded loudly.
    """
    root = Path(repo) if repo else Path(__file__).resolve().parents[2]
    sha = _git("rev-parse", "HEAD", repo=root)
    status = _git("status", "--porcelain", repo=root)
    return {
        "sha": sha,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", repo=root),
        "dirty": bool(status) if status is not None else None,
    }


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in _TRACKED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    # torch's build string distinguishes CPU from cu121 etc.
    if "torch" in versions:
        try:
            import torch

            versions["torch"] = torch.__version__
            versions["torch.cuda_available"] = str(torch.cuda.is_available())
        except Exception:  # provenance must never break a run
            pass
    return versions


def env_info() -> dict[str, object]:
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.machine(),
        "packages": package_versions(),
    }
