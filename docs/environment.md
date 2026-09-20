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
| torch | not installed yet — Phase 1 |

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

## torch is deliberately not in any lock

CPU and CUDA wheels come from different indexes and are different builds. If
torch were pinned in the lock, a laptop run and a Colab run would silently be
different software under the same version string.

```bash
# laptop
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
# Colab (CUDA already present)
uv pip install torch
```

`src/common/provenance.py` records `torch.__version__` and
`torch.cuda.is_available()` into every results JSON, so two runs can always be
told apart after the fact.

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
