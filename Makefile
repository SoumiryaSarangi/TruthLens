# TruthLens task runner.
#
# Targets are deliberately single commands with no shell conditionals or &&
# chains: GNU Make 3.81 on Windows runs recipes through cmd.exe, and anything
# fancier silently behaves differently there than it does in CI.
#
#   make setup      provision Python 3.11 and install the pinned core deps
#   make eval       CONFIG=configs/<name>.yaml -- the only way to get a number
#   make test       full test suite
#   make lint       ruff
#   make leakage    leakage + frozen-split checks (run after ANY data change)
#   make table      render results/*.json into markdown
#   make status     what is in data/splits/
#   make lock       (re)write data/splits/SPLITS.lock
#   make fixtures   regenerate the toy test fixtures

ifeq ($(OS),Windows_NT)
    PY ?= .venv/Scripts/python.exe
else
    PY ?= .venv/bin/python
endif

# Windows consoles default to cp1252 and choke on Devanagari/Gurmukhi output.
export PYTHONIOENCODING = utf-8
# src/ is the package root; set here so targets work without an editable install.
export PYTHONPATH = src

CONFIG ?= configs/example_majority_baseline.yaml

.PHONY: setup setup-ml eval test lint fix leakage table status lock fixtures clean help

help:
	@echo "make setup | eval CONFIG=... | test | lint | leakage | table | status | lock"

setup:
	uv python install 3.11
	uv venv --python 3.11
	uv pip sync requirements.txt requirements-dev.txt
	uv pip install -e . --no-deps
	$(PY) -m pre_commit install

# Phase 1+. torch is installed separately so the CPU and CUDA builds stay explicit.
setup-ml:
	uv pip install -r requirements-ml.txt
	@echo "Now install torch for THIS machine, e.g.:"
	@echo "  uv pip install torch --index-url https://download.pytorch.org/whl/cpu"

eval:
	$(PY) -m eval.evaluate --config $(CONFIG)

test:
	$(PY) -m pytest tests/ -q

lint:
	$(PY) -m ruff check src/ tests/ scripts/

fix:
	$(PY) -m ruff check --fix src/ tests/ scripts/

# CLAUDE.md: run after ANY data change.
leakage:
	$(PY) -m pytest tests/test_no_leakage.py tests/test_splits_frozen.py -q

table:
	$(PY) -m eval.report --out docs/results.md

status:
	$(PY) scripts/build_splits.py status

lock:
	$(PY) scripts/build_splits.py lock

fixtures:
	$(PY) scripts/make_fixtures.py

clean:
	$(PY) -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
