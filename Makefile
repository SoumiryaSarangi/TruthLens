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
#   make data       download raw sources and rebuild splits + profile
#   make kb         download the AVeriTeC dev knowledge store (11.5 GB, resumable)
#   make profile    regenerate docs/data-profile.md from the frozen splits
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

.PHONY: setup setup-ml download kb data profile eval test lint fix leakage table status lock fixtures clean help

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
	uv pip install "torch==2.9.1" --index-url https://download.pytorch.org/whl/cu128
	uv pip install -r requirements-ml.txt
	$(PY) -c "import torch; assert '+cu' in torch.__version__, 'CPU torch got installed: ' + torch.__version__; print('OK', torch.__version__, 'cuda', torch.cuda.is_available())"

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

download:
	$(PY) scripts/download_data.py

# 11.5 GB, resumable. Safe to interrupt and rerun. Phase 1 evidence retrieval.
kb:
	$(PY) scripts/download_knowledge_store.py --split dev

kb-list:
	$(PY) scripts/download_knowledge_store.py --list

# Full data pipeline: fetch, materialise into frozen splits, profile, check.
data: download
	$(PY) scripts/build_splits.py build
	$(PY) scripts/profile_data.py
	$(PY) -m pytest tests/test_no_leakage.py tests/test_splits_frozen.py -q

profile:
	$(PY) scripts/profile_data.py

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
