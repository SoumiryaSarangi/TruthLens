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


# Paths whose state cannot change what a run computes. `results/` holds the
# OUTPUTS of runs, so an uncommitted results file from the eval two minutes ago
# says nothing about whether this eval is reproducible.
_IRRELEVANT_TO_REPRODUCIBILITY = ("results/",)


def _status_paths(status: str) -> list[str]:
    """Paths from `git status --porcelain`, forward-slashed, renames resolved."""
    paths: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:                    # a rename: the destination is what counts
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip('"').replace("\\", "/"))
    return paths


def git_info(repo: str | Path | None = None) -> dict[str, object]:
    """Current commit and whether the tree was dirty when the run happened.

    `dirty: true` means the committed code does not reproduce that number. It is
    recorded rather than blocked, but it is recorded loudly.

    **Changes under `results/` do not count.** Until 2026-09-24 they did, and the
    consequence was that all 31 results files in the repo carried `dirty: true`
    -- because writing one results file makes the tree dirty for the next eval in
    the same batch. A flag that fires on every run carries no information, and
    `docs/results.md` printed "dirty tree" in the Flags column of every row,
    which teaches a reader to ignore that column. Results are outputs; they
    cannot change what a run computes. Everything else still counts, including
    untracked source files, which very much can.
    """
    root = Path(repo) if repo else Path(__file__).resolve().parents[2]
    sha = _git("rev-parse", "HEAD", repo=root)
    status = _git("status", "--porcelain", repo=root)
    if status is None:
        dirty: bool | None = None
    else:
        dirty = any(
            not path.startswith(_IRRELEVANT_TO_REPRODUCIBILITY)
            for path in _status_paths(status)
        )
    return {
        "sha": sha,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", repo=root),
        "dirty": dirty,
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
