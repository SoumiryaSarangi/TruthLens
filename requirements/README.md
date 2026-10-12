# Python requirements

Three layers, each a human-edited `.in` file and a machine-generated, **hash-pinned** `.txt` lock. Edit the `.in`, never
the `.txt`; the install always uses the `.txt`.

| Lock | Source | What it holds | Needed for |
| --- | --- | --- | --- |
| `core.txt` | `core.in` | `pyyaml`, `jsonschema`, `numpy`, `pydantic`: the evaluation harness and contracts | everything; the only layer CI installs for the main checks |
| `dev.txt` | `dev.in` | `pytest`, `ruff`, `pre-commit`, `scikit-learn` (a test oracle) | development and CI |
| `ml.txt` | `ml.in` | `transformers`, `sentence-transformers`, `faiss`, `fastText`, FastAPI, PEFT, and the rest of the model stack | **running the app** and the models; not CI |

`torch` is deliberately **not** in `ml.txt`. It is installed from the PyTorch index so the CUDA build is never replaced by a
CPU one (`make setup-ml` does this and then asserts the build string contains `+cu`).

## Which do I install?

| I want to... | Install |
| --- | --- |
| Run the web app / the pipeline | `core` + `dev` + `ml` (`make setup` then `make setup-ml`, or the commands below) |
| Run the tests and linter only | `core` + `dev` |
| Run the evaluation harness only | `core` |

Without `make` (the same thing, in PowerShell on Windows):

```powershell
uv python install 3.11
uv venv --python 3.11
uv pip sync requirements/core.txt requirements/dev.txt
uv pip install -e . --no-deps
uv pip install "torch==2.9.1" --index-url https://download.pytorch.org/whl/cu128
uv pip install -r requirements/ml.txt
```

Use `uv pip sync` only for `core` + `dev`: `sync` makes the environment match exactly, so syncing afterwards would remove
the ML packages. Add the ML layer with `uv pip install -r`.

## Regenerating a lock

Only when you change a `.in` file. From the repository root:

```bash
uv pip compile requirements/core.in -o requirements/core.txt --generate-hashes --python-version 3.11
uv pip compile requirements/dev.in  -o requirements/dev.txt  --generate-hashes --python-version 3.11
uv pip compile requirements/ml.in   -o requirements/ml.txt   --generate-hashes --python-version 3.11 --no-emit-package torch
```

`dev.in` and `ml.in` constrain themselves to `core.txt` (`-c core.txt`), so regenerate `core` first. After regenerating
`ml.txt`, check that torch is still a CUDA build. The reasons and the history are in
[`../docs/environment.md`](../docs/environment.md).

## Other files at the repository root

| File | What it is |
| --- | --- |
| `pyproject.toml` | the project and tool configuration (ruff, pytest). Dependencies are *not* listed here; they come from the locks. |
| `uv.lock` | a stub that uv writes for the project itself (the package, no dependencies). Harmless; it is not the dependency lock. |
| `package.json`, `package-lock.json` | the front-end build only: the shader-gradient bundle (`npm run build:rail`). A server does not need Node. |
