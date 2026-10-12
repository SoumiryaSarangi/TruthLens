# Operations runbook

How to run TruthLens, what it needs, and what to do when it misbehaves. Everything under "Troubleshooting" is a failure
that actually happened while building this project.

## Requirements

| | |
| --- | --- |
| OS | Windows 11 is the tested platform; Linux should work but is untested |
| Python | 3.11 via uv (the system Python 3.13 is unsupported) |
| GPU | one NVIDIA GPU with 6 GB VRAM, CUDA build of PyTorch (tested: RTX 4050 Laptop) |
| RAM | 16 GB recommended; about 1.4 GB of free RAM beside the running server was not enough to load another model process |
| Network | needed only for the live look-up and for first-time model downloads |

## Starting and stopping

```powershell
.\.venv\Scripts\python.exe scripts\serve.py     # Windows: works in every shell
```

```bash
.venv/bin/python scripts/serve.py                # Linux / macOS
make serve                                       # the same launcher, where make works
```

- `scripts/serve.py` listens on `127.0.0.1:8000`; running `python -m app.main` instead honours the `PORT` variable. Ready for offline checks after about a minute (a warm-up request
  runs every stage once); the live-check models load in the background and are warm after about 40 s more.
- Stop with Ctrl+C in its terminal. A leftover process on port 8000 is the usual reason a new one will not bind.
- `GET /health` shows which stages loaded; `GET /version` shows the git SHA and the served configuration, which is the
  quickest way to confirm which build you are talking to.

## Configuration and secrets

- Served settings: `configs/pipeline/dev.yaml` (see the README table). Restart the server after editing it.
- `.env` (git-ignored, copy from `.env.example`): `GOOGLE_FACTCHECK_API_KEY` enables Google Fact Check in the live look-up.
  Without it the live look-up still uses Wikipedia and says the other source was skipped.

## Resource model

The served stack fits a 6 GB GPU by design (about 4.6 of the roughly 4.9 GiB Windows leaves usable). The NLI and translation
models for the live check are kept in CPU memory and moved to the GPU only while a request runs. The shader gradient is
throttled (20 frames a second, 5 while a check is running) so it does not compete with them; unthrottled, it slowed a
fast check from 1.1 s to 2.6 s on the reference machine.

**Do not run a second GPU process while the server is up.** Stop the server first for: `scripts/demo_check.py`,
`tests/test_orchestrator.py`, any script that loads a model.

## Checks before a demo

1. Stop the server, then run `python scripts/demo_check.py`. It must print `OK: every chip shows its path and no
   regression verdict moved`.
2. Start the server, wait for the warm-up, and press one online check so the live models are loaded.
3. Open the page, hard-refresh (Ctrl+Shift+R), and try each example chip.

## Troubleshooting

### "TruthLens could not finish checking this message" on every request
**Cause seen:** a CUDA out-of-memory error during the start-up warm-up of the live models left the process unusable, so
every request, including offline ones, failed (`torch.AcceleratorError: CUDA error: out of memory` in the server log).
**Fix:** stop the server, confirm the GPU is free (`nvidia-smi` shows about 0 MiB), start it again and wait for the
`warm-up request done` line before the first request. If it recurs, close other GPU programs (browsers with hardware
acceleration, other model processes).

### The page still looks like an old version
**Cause seen:** the browser cached the old stylesheet and script. The server now sends `Cache-Control: no-cache`, so this
should not recur; once, do a hard refresh (Ctrl+Shift+R), or open the page in a private window. Confirm the build with
`/version`.

### A script crashes with a segmentation fault or an access violation while loading a model
**Cause seen:** another process (the server) is holding the GPU and most of the free RAM. **Fix:** stop the server and
re-run. Setting `CUDA_VISIBLE_DEVICES=""` runs a script on the CPU, which is slow and can still fail on memory.

### Garbled or crashing console output (Devanagari, Gurmukhi)
Windows consoles default to cp1252. Run through `make`, or set `PYTHONIOENCODING=utf-8`.

### Port 8000 is already in use
Find the owner with `Get-NetTCPConnection -LocalPort 8000` (PowerShell) and stop that process, or run `python -m app.main` with `PORT` set to another port.

### The live look-up says it is unavailable, or a trace shows `degraded: ... HTTP 429/503`
The source (Wikipedia or Google) throttled or was down. The card keeps its offline answer and says so; retry later.
Fetched pages are cached on disk and the fetcher spaces and retries calls, so repeated checks are cheap.

### "No Google Fact Check key configured"
Create `.env` from `.env.example`. Never paste the key into a command line or a log.

### `uv: command not found`
`uv` can disappear from PATH. Reinstall it (`irm https://astral.sh/uv/install.ps1 | iex`) and make sure its bin directory is
on PATH; an existing `.venv` keeps working without it.

### The disk filled up
Headless-browser scratch profiles and model caches are the usual causes. Browser test scripts should delete their profile
folder; clear `%TEMP%\cdp-*` if they did not. Model caches live under the Hugging Face cache directory (21 GB on the
reference machine).

### Tests: `tests/test_orchestrator.py` crashes or runs out of memory
Run the suite in two parts, with the server stopped:
`pytest tests --ignore=tests/test_orchestrator.py` then `pytest tests/test_orchestrator.py`.

## Rebuilding the front-end bundle

Only when `ui-src/` changes:

```bash
npm install
npm run build:rail     # writes app/static/vendor/rail-shader.js; commit the result
node scripts/make_icons.js   # only if favicon.svg changes; then build favicon.ico from icon-512.png with Pillow
```

## Backup and state

There is no database. State is: the git repository, `results/` (every measurement), the git-ignored data and index
directories (rebuildable with `make data`, except access-restricted MultiClaim and the owner's private claim files, which
must be backed up separately), and the live fetch cache (disposable).
