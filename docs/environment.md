# Environment

How to reproduce the environment these numbers came from. Every
`results/*.json` also carries an `env` block with the interpreter, platform
and package versions of that specific run, so this file is the setup
instructions and the JSON is the record.

## Resolved on this machine

| | |
| --- | --- |
| Python | `Python 3.11.16` (provisioned by uv, not the system Python) |
| uv | `uv 0.12.17 (635500036 2026-09-18 x86_64-pc-windows-msvc)` |
| GNU Make | `GNU Make 3.81` |
| Platform | Windows 11, x86_64 |
| GPU | NVIDIA RTX 4050 laptop, **6 GB VRAM** (inference ceiling 5.5 GB, NFR-3) |
| CPU | Intel i7-14700HX |
| torch | **not installed yet** — Phase 1. Install the **CUDA** build, then record the resolved build string here |

The system Python on this machine is 3.13, which the stack does not support.
`uv python install 3.11` fetches its own interpreter, so the system one is
left alone.

## Setup from a clean clone

```bash
winget install --id astral-sh.uv -e          # once
winget install --id GnuWin32.Make -e         # once; add its bin dir to PATH
make setup
```

`make setup` runs `uv python install 3.11`, creates `.venv`, installs the
hash-pinned core and dev locks, installs the project editable, and wires up
pre-commit.

Verify:

```bash
make lint
make test
make eval CONFIG=configs/example_majority_baseline.yaml
```

## Dependency locks

Three files, each compiled with `uv pip compile --generate-hashes` against
Python 3.11. Edit the `.in`, never the `.txt`.

| Lock | Contents | Installed when |
| --- | --- | --- |
| `requirements.txt` | pyyaml, jsonschema, numpy | always — the harness runs on this alone |
| `requirements-dev.txt` | pytest, ruff, pre-commit, scikit-learn | always |
| `requirements-ml.txt` | transformers, sentence-transformers, faiss, fastText, FastAPI | Phase 1 (`make setup-ml`) |

The core lock is kept tiny on purpose: CI and `make leakage` install in
seconds, so there is never a reason to skip the leakage check.

scikit-learn is a **dev** dependency, not a runtime one. It is the independent
oracle in `tests/test_metrics.py`; `src/eval/metrics.py` implements its own
macro-F1 and the test asserts the two agree. A metric checked against itself
is not checked.

To re-resolve after editing a `.in`:

```bash
uv pip compile requirements.in     -o requirements.txt     --generate-hashes --python-version 3.11
uv pip compile requirements-dev.in -o requirements-dev.txt --generate-hashes --python-version 3.11
uv pip compile requirements-ml.in  -o requirements-ml.txt  --generate-hashes --python-version 3.11
```

## torch: install the CUDA build

This machine has an **NVIDIA RTX 4050 laptop GPU, 6 GB VRAM**. Install the CUDA
build. Installing the CPU build is the expensive mistake here: everything still
works, nothing errors, training is just twenty times slower, and on a 14-day
timeline that is most of the project.

```bash
# NOT YET INSTALLED - this is the Phase 1 setup step
uv pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Pick the `cuXXX` index that matches the driver; check with `nvidia-smi`. If the
driver is older than the wheel's CUDA runtime, step down one minor version rather
than upgrading the driver mid-project.

**Verify it, don't assume it.** A CPU wheel installs perfectly happily:

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

`cuda.is_available()` must be `True` and the device name must say RTX 4050. Then
**record the resolved build string in the table at the top of this file** — the
exact `torch.__version__` (e.g. `2.x.x+cu124`) — so a number produced today can
be told apart from one produced after an upgrade.

`src/common/provenance.py` already stamps `torch.__version__` and
`torch.cuda.is_available()` into every results JSON, so the record is automatic
per run; this file is the human-readable copy.

### Why torch is in no lock file

CPU and CUDA wheels come from different indexes and are genuinely different
builds. Pinning one would mean this laptop and CI run different software under
the same version string — and CI deliberately has no torch at all, since the
fast job installs the core lock only.

### VRAM budget

`SRS.md` NFR-3 sets an inference ceiling of **5.5 GB**, leaving headroom on the
6 GB card. `SYSTEM_DESIGN.md` §10 estimates ~2.8 GB of resident weights. That is
an estimate, not a measurement: once models load, measure with
`torch.cuda.max_memory_allocated()` and write the real figure into this file.
Training runs one model at a time, with the API server stopped (NFR-4).

## Windows gotchas

- **Console encoding.** Windows terminals default to cp1252 and raise
  `UnicodeEncodeError` on Devanagari or Gurmukhi output. The Makefile exports
  `PYTHONIOENCODING=utf-8`; if running Python directly, set it yourself.
- **GnuWin32 Make does not add itself to PATH.** Its binary is at
  `C:\Program Files (x86)\GnuWin32\bin\make.exe`.
- **Make 3.81 is from 2006** and runs recipes through `cmd.exe` when no `sh`
  is present. Every Makefile recipe is therefore a single command with no
  `&&`, conditionals or shell functions. Keep it that way.
- **Line endings.** `.gitattributes` marks `*.jsonl` and `data/splits/**` as
  `-text` so git never rewrites a byte of a frozen split. Without this the
  sha256 in `SPLITS.lock` would differ between Windows and CI.

## Seeds

`src/common/seeds.py:set_all_seeds` is the only place a seed is set; it
returns which libraries it actually reached, and that record goes into the
results JSON as `seeded_libraries`. It imports torch and transformers lazily,
so it works in Phase 0 where neither is installed.
