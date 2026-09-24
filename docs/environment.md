# Environment

How to reproduce the environment these numbers came from. Every
`results/*.json` also carries an `env` block with the interpreter, platform
and package versions of that specific run, so this file is the setup
instructions and the JSON is the record.

## Resolved on this machine

| | |
| --- | --- |
| Python | `Python 3.11.16` (provisioned by uv, not the system Python) |
| uv | `uv 0.12.18 (01cb90c1a 2026-09-22 x86_64-pc-windows-msvc)` |

> **`uv` went missing from this machine once** (Day 3), and nothing failed
> until something needed installing -- the existing `.venv` keeps working
> without it. If `make setup` reports `uv: command not found`, reinstall with
> `irm https://astral.sh/uv/install.ps1 | iex` and check that
> `%USERPROFILE%\.localin` is on PATH.
| GNU Make | `GNU Make 3.81` |
| Platform | Windows 11, x86_64 |
| GPU | NVIDIA RTX 4050 laptop, **6 GB VRAM** (inference ceiling 5.5 GB, NFR-3) |
| CPU | Intel i7-14700HX |
| torch | **`2.9.1+cu128`** — CUDA build, verified on the RTX 4050 (installed 21 Sep 2026) |

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

This was **not actually true until 21 Sep 2026**: `requirements-ml.txt` pinned
`torch==2.14.0`, pulled in as a dependency of `sentence-transformers` and
`transformers`. On Windows the PyPI wheel is CPU-only, so `uv pip install -r
requirements-ml.txt` would have silently replaced the CUDA build with a CPU one
— the exact failure this section warns about, sitting inside the lock that was
supposed to prevent it. The lock is now compiled with:

```bash
uv pip compile requirements-ml.in -o requirements-ml.txt     --generate-hashes --python-version 3.11 --no-emit-package torch
```

Keep the `--no-emit-package torch` flag on every recompile. After any
`uv pip install -r requirements-ml.txt`, check that torch is still a `+cu` build:

```bash
python -c "import torch; assert '+cu' in torch.__version__, torch.__version__"
```

### VRAM budget — measured, and smaller than the spec assumes

`SRS.md` NFR-3 sets an inference ceiling of **5.5 GB** on a 6 GB card.
**Measured on an idle desktop, only 4.96 GiB of the 6.00 GiB is actually
free** — Windows WDDM reserves roughly 1 GiB for desktop compositing, and that
reservation grows with a browser or a second monitor.

So treat **~4.9 GiB as the real ceiling**, not 5.5 GB. `SYSTEM_DESIGN.md` §10
estimates ~2.8 GB of resident weights, which still fits, but the headroom is
about 2 GiB rather than the 2.7 GB the spec implies. That is the margin
activations have to live in.

```bash
python -c "import torch; f,t=torch.cuda.mem_get_info(); print(f'free {f/1024**3:.2f} / {t/1024**3:.2f} GiB')"
```

Practical consequences:

- Close the browser before a training run. It is worth several hundred MB.
- Measure with `torch.cuda.max_memory_allocated()` once models actually load,
  and write the real figure here rather than trusting §10's estimate. **Done in
  Phase 3** — see *Measured training cost* below. §10's estimate holds: the
  heaviest run peaks at 2.588 GiB.
- Training runs one model at a time with the API server stopped (NFR-4). On
  this card that is a hard requirement, not hygiene.
- If a model will not fit, the order to try is: smaller batch, gradient
  checkpointing, then 4-bit — not a smaller model, which changes the result.

## Caches live on D:, not C:

**C: was 100% full (1.5 GB free of 245 GB)** while every tool cached there by
default. The first model download would have failed on Day 1, for a reason
nobody would have connected to disk space.

Cleared 12.6 GB of rebuildable cache (`uv cache clean`, `pip cache purge`) and
redirected all three caches to D:, set as **user environment variables** so
they persist across shells:

| Variable | Value | Was |
| --- | --- | --- |
| `HF_HOME` | `D:\hf-cache` | `C:\Users\ss\.cache\huggingface` |
| `UV_CACHE_DIR` | `D:\uv-cache` | `C:\Users\ss\AppData\Local\uv\cache` |
| `PIP_CACHE_DIR` | `D:\pip-cache` | `C:\Users\ss\AppData\Local\pip\Cache` |

Models therefore land in `D:\hf-cache\hub`, where the ~17 GB of weights will
go. Verified with a real download: `hf_hub_download('ai4bharat/IndicBART',
'config.json')` resolved under `D:\hf-cache\hub\models--ai4bharat--IndicBART\`.

These caches sit **outside the project directory on purpose** — a `git clean
-xdf` in the repo must never be able to delete 17 GB of model weights.

**A shell opened before these were set does not have them.** That is not
hypothetical: it already sent one model to `C:` after the change. If a download
lands in the wrong place, check `echo $HF_HOME` in that shell rather than
assuming the variable did not take.

Symlinks are permitted on this machine, so the HF cache stores each blob once
instead of duplicating it. Worth checking rather than assuming: without
Developer Mode, Windows silently doubles the cache.

## Models downloaded so far

Cached under `D:\hf-cache\hub`. Sizes are what actually landed on disk, not the
repo totals the Hub reports.

| Model | Role | On disk |
| --- | --- | --- |
| `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | Phase 1 stance, via NLI | ~0.6 GB |
| `ai4bharat/IndicBART` | Phase 6 generation (config only so far) | config |
| `google/muril-base-cased` | Phase 2 embedding ladder, rung 3 | ~1.0 GB |
| `sentence-transformers/LaBSE` | Bitext alignment + the t-SNE figure only | ~1.9 GB |
| `BAAI/bge-m3` | Retrieval and claim matching (the winner) | ~2.3 GB |

Total HF cache after Phase 2: **8.3 GB**. Two more model files live outside it,
under gitignored `data/raw/`, because they are *data* the splits and evals are
built from and `DOWNLOADS.json` records their sha256:

| File | Role | On disk |
| --- | --- | --- |
| `data/raw/fasttext/lid.176.bin` | Language ID (FR-3) | 131 MB |
| `data/raw/dakshina/dakshina_dataset_v1.0.tar` | Transliteration benchmark | 2.01 GB |

Several models are **ours**, trained here and written to gitignored
`data/interim/models/`:

| Model | Built by | On disk |
| --- | --- | --- |
| `roman_lid.joblib` -- char n-gram language ID for Latin script | `scripts/train_roman_lid.py` | 4.5 MB |
| `word2vec.kv` -- in-domain static embeddings | `scripts/train_word2vec.py` | 80 MB |
| `span_xlmr_{joint,mono_en,mono_hi,mono_pa,zeroshot}` -- LoRA span taggers | `scripts/train_span.py` | 20 MB each |
| `checkworthy_xlmr` -- LoRA sequence classifier | `scripts/train_checkworthy.py` | 22 MB |

### Where fine-tuned checkpoints live, and why not in git

LoRA adapters go to gitignored `data/interim/models/<name>/`, following the
precedent `roman_lid.joblib` and `word2vec.kv` set. Three reasons, in order of
weight: they are **reproducible** from a seeded script plus a frozen split, so
committing them stores an output rather than an input; 20 MB times six arms is
120 MB of binary in a repo whose entire point is that it holds ids and not
payloads; and an adapter in git would be a second source of truth about what a
number came from, next to the `results/*.json` that already records the config
hash. Each directory carries a `training.json` with the seed, the hyper
parameters, the row counts and the measured peak VRAM, which is what a reader
actually needs to rebuild it.

Only the **adapter** is stored -- 3.5 MB of `adapter_model.safetensors` for
887K trainable parameters out of XLM-R-base's 278M (0.32%). The base model
comes from the HF cache on D:.

### Measured training cost (RTX 4050, XLM-R-base + LoRA, fp16, batch 16, len 256)

`SYSTEM_DESIGN.md` §10 estimated **~2.8 GB resident** and nobody had checked
it. Measured with `torch.cuda.max_memory_allocated()` and recorded per run in
`data/interim/models/*/training.json`:

| Run | Train rows | Peak VRAM | Wall clock |
| --- | --- | --- | --- |
| Span, joint (en+hi+pa) | 4,472 | **2.587 GiB** | 3.0 min |
| Span, zero-shot (en+hi) | 4,135 | 2.579 GiB | 4.2 min |
| Span, mono-en | 2,977 | 2.579 GiB | 2.9 min |
| Span, mono-hi | 1,158 | 2.587 GiB | 0.7 min |
| Span, mono-pa | 337 | 2.448 GiB | 0.2 min |
| Check-worthiness classifier | 7,874 | 2.588 GiB | 4.9 min |

**So §10's estimate was right**, which is worth stating in the document that
made it. Two things the table shows that the estimate could not:

- Peak VRAM is **flat in dataset size** -- 337 rows and 7,874 rows both peak
  near 2.58 GiB. It is set by batch size times sequence length, so the knob
  that matters if a future run will not fit is `--batch-size`, exactly as the
  order above prescribes. The first run did not OOM at batch 16 and no halving
  was needed.
- Against the **~4.9 GiB real ceiling**, training leaves ~2.3 GiB of headroom,
  and training peaks about 1.5 GiB above the heaviest inference workload
  measured here (BGE-M3 at 1.11 GiB). Training is the binding constraint on
  this card, not serving.

### Measured encoder throughput (RTX 4050, 78,077 documents, fp16, batch 32)

| Encoder | Time | Peak VRAM | Index |
| --- | --- | --- | --- |
| BGE-M3 (1024-d) | 12.1 min | 1.11 GiB | 160 MB |
| LaBSE (768-d) | 2.4 min | 0.97 GiB | 120 MB |
| MuRIL (768-d) | 3.7 min | 0.52 GiB | 120 MB |
| TF-IDF (512-d) | 4.0 min (CPU, SVD) | -- | 80 MB + 606 MB state |
| Word2Vec (300-d) | 0.1 min (CPU) | -- | 47 MB |

Against **4.96 GiB free** of the card's 6.00 GiB. Comfortably inside
`SYSTEM_DESIGN.md` 7's 3 GB index budget and 10's VRAM ceiling.

### `fasttext-wheel` 0.9.2 is broken under NumPy 2

Its `predict()` ends in `np.array(probs, copy=False)`, which NumPy 2 raises on
instead of silently copying -- so every call through the documented API throws.
`src/preprocess/lid.py` calls the C++ predictor (`model.f.predict`) directly.
The alternative was pinning NumPy back for the whole project because of one
wrapper line. Do not "simplify" it back.

The NLI model's label order is read from its own config at load time rather
than assumed — `{0: entailment, 1: neutral, 2: contradiction}` — because
getting it backwards would invert every verdict while everything still ran and
produced plausible-looking numbers. `src/stance/nli.py` raises if the config
carries a label it does not recognise.

## Downloading from the HuggingFace Hub is unreliable here

Not blocked — **intermittent**. Measured twice in one session:

| Endpoint | Sample 1 | Sample 2 |
| --- | --- | --- |
| `huggingface.co` | 0/12 | 5/10 |
| `hf.co` | worked | 4/10 |

Neither hostname is reliably better; the connection is simply bad. So:

- **Expect any multi-GB download to be interrupted several times.** Use
  something that resumes. `huggingface_hub` resumes partial downloads by
  default, and `scripts/download_knowledge_store.py` does its own Range
  resumption with backoff.
- **Do not "fix" a failed download by switching hostname or starting over.**
  Rerun and let it resume.
- Setting `HF_TOKEN` raises the rate limit and is worth doing before pulling
  ~17 GB of models, though it will not help with the dropped connections.

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
