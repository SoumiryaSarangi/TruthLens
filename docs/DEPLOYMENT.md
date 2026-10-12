# Deployment guide

How to put TruthLens somewhere other than the development laptop. Read **"What is and is not verified"** first: the
procedure in section 4 was tested end to end from a clean export on the development machine; the cloud, Linux and tunnel
steps were not, and are marked.

## 1. Reality check

TruthLens is a model-serving application, not a small web app. Plan around these facts.

| | |
| --- | --- |
| **GPU** | One NVIDIA GPU with **6 GB or more** VRAM is the supported target (tested: RTX 4050 Laptop, 6 GB). The served stack uses about 4.6 GiB. |
| **RAM** | 16 GB recommended. About 1.4 GB free beside a running server was not enough to load a second model process. |
| **Disk** | About 2.1 GB of packaged runtime data (1.5 GB zipped) plus roughly 10 GB of models that download on first start (an estimate: the development cache holds 21 GB including unrelated models), plus the Python environment (about 5 GB). Plan **30 GB** of free disk. |
| **Start-up** | About a minute for offline answers; the live-check models load in the background after that, and the first online check can take 10 to 20 seconds. |
| **Throughput** | One server process, one GPU: checks are effectively served one at a time. Observed on the clean-room run: fast path and offline answers 0.1 to 2.4 s, a live check 4 to 7 s once warm, the very first request 16 s. This is a single-reader tool, not a high-traffic service. |
| **Authentication** | **None.** Anyone who can reach the port can spend your Google quota and your GPU. Put authentication in front of it before it faces a network (section 6). |
| **Licences** | The verdict components were trained on AVeriTeC (CC BY-NC 4.0) and the translator is non-commercial. A *public commercial* deployment is not covered; see [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). |

## 2. Choose a route

| Route | Best for | Effort | Cost | Public? |
| --- | --- | --- | --- | --- |
| **A. Your own GPU machine, shared through a tunnel** | a viva, a demo, a few testers | 15 minutes | free | a temporary URL |
| **B. A rented GPU machine (cloud VM)** | a link that stays up | 1 to 2 hours | a GPU instance by the hour (check current pricing) | yes |
| **C. CPU only** | not recommended | n/a | n/a | n/a |

Route C is listed so it is not a surprise: on a CPU the claim translation alone took 6 to 13 seconds per claim in the
project's spike, and the two large NLI models are slower still. The page would work but a live check would take a minute
or more. It is untested here, so do not plan on it.

**If you only need it live for a demonstration, use route A.** It reuses the machine that already works.

## 3. What you are shipping

The repository holds code and configuration. The served application also needs **git-ignored data**, which is rebuilt and
not committed. `scripts/package_runtime.py` gathers exactly those files:

```bash
python scripts/package_runtime.py --dry-run          # list the files and sizes
python scripts/package_runtime.py --out dist/truthlens-runtime.zip     # 2.1 GB uncompressed, 1.5 GB zipped
```

| In the archive | Why |
| --- | --- |
| `data/interim/index/` (embeddings, rating metadata, ids, lexical corpus) | the fact-check fast path |
| `data/interim/evidence/` | the demo evidence corpus and its indexes |
| `data/interim/models/` (aggregator, check-worthiness, span, explainer adapters, romanized-LID) | the small trained components |
| `data/raw/fasttext/lid.176.bin` | language identification |
| `data/raw/dakshina/extracted/` | the transliteration lexicon |

**Not in the archive, on purpose:**

- `.env` (the Google Fact Check key). Create it on the target machine; never put it in an archive or an image.
- The Hugging Face model cache. Models download on first use (needs internet once); you can pre-seed `HF_HOME` to
  avoid that.
- `data/private/` and every evaluation dataset. A deployment needs none of them.

## 4. Route B: a GPU machine, step by step

The steps are written for Ubuntu 22.04 with an NVIDIA GPU. A Windows GPU machine follows the same shape using the commands
in the README (that is the platform the project was built and tested on).

### 4.1 Provision

Create a GPU instance with at least 6 GB of VRAM, 16 GB of RAM and 40 GB of disk (a T4-class GPU is a typical minimum).
Open **only** SSH (22) and, for HTTPS, 443 in its firewall. Do not open port 8000 to the internet.

```bash
nvidia-smi             # must list the GPU and a driver; install the vendor driver first if it does not
```

### 4.2 Install the tooling

```bash
sudo apt-get update && sudo apt-get install -y git make unzip
curl -LsSf https://astral.sh/uv/install.sh | sh        # then open a new shell, or: source ~/.local/bin/env
```

### 4.3 Get the code and the environment

```bash
git clone https://github.com/SoumiryaSarangi/TruthLens.git && cd TruthLens
make setup           # uv provisions Python 3.11 and the hash-pinned core and dev locks
make setup-ml        # CUDA build of PyTorch (cu128) and the ML lock; prints "OK <version> cuda True"
```

> **Linux is untested.** The locks were generated on Windows. PyTorch comes from its own index (so the CUDA build is
> right), and the ML lock lists hashes for every distribution of each pinned version, so it should resolve on Linux, but
> that was not verified. If `make setup-ml` fails on a package, report which and use `uv pip install` for that one.

### 4.4 Bring the data

From the machine that has it:

```bash
python scripts/package_runtime.py --out dist/truthlens-runtime.zip
scp dist/truthlens-runtime.zip user@SERVER:~/TruthLens/
```

On the server:

```bash
cd ~/TruthLens && unzip -o truthlens-runtime.zip && rm truthlens-runtime.zip
```

### 4.5 Configure

```bash
cp .env.example .env && chmod 600 .env     # then set GOOGLE_FACTCHECK_API_KEY=...  (optional but recommended)
```

Without the key the live look-up still uses Wikipedia and says the fact-check source was skipped. The key is a free
Google Cloud "Fact Check Tools API" key; restrict it to that API in the console.

Optional environment (put in the service file, section 4.7):

| Variable | Purpose | Default |
| --- | --- | --- |
| `TRUTHLENS_HOST` | interface to bind. Keep `127.0.0.1` when a reverse proxy on the same machine faces the network. | `127.0.0.1` |
| `PORT` | port | `8000` |
| `TRUTHLENS_WARMUP` | load every model before the first request | `1` (set by `serve.py`) |
| `TRUTHLENS_GIT_SHA` | the build string `/version` reports when there is no `.git` | none |
| `HF_HOME` | where models are cached | the Hugging Face default |

### 4.6 Smoke test (before any service or proxy)

```bash
make serve &                                   # or: .venv/bin/python scripts/serve.py
sleep 90 && curl -s localhost:8000/health      # {"status":"ok","stages":{... "loaded"}}
curl -s localhost:8000/verify -H 'Content-Type: application/json' \
  -d '{"text":"Pineapple juice is 500 times more effective at stopping a cough than cough syrup","include_trace":false}' \
  | head -c 300
```

Expect `"path":"fast"` and `"verdict":"Refuted"`. If startup logs `CUDA error: out of memory`, stop it, check
`nvidia-smi` is idle, and start again ([`OPERATIONS.md`](OPERATIONS.md)).

### 4.7 Run it as a service

```ini
# /etc/systemd/system/truthlens.service
[Unit]
Description=TruthLens
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/TruthLens
Environment=TRUTHLENS_HOST=127.0.0.1 PORT=8000 PYTHONIOENCODING=utf-8 TRUTHLENS_GIT_SHA=<commit>
ExecStart=/home/ubuntu/TruthLens/.venv/bin/python scripts/serve.py
Restart=on-failure
RestartSec=10
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now truthlens
journalctl -u truthlens -f        # watch for "warm-up request done" then "Application startup complete"
```

Run **one** instance. A second would compete for the same GPU memory and fail.

### 4.8 HTTPS and a password (reverse proxy)

Use any proxy that terminates TLS and adds authentication. Caddy is the shortest:

```bash
sudo apt-get install -y caddy
caddy hash-password            # type a password; copy the hash
```

```caddyfile
# /etc/caddy/Caddyfile        (your-domain.example must point at the server)
your-domain.example {
    basic_auth {
        reader PASTE_THE_HASH_HERE
    }
    reverse_proxy 127.0.0.1:8000
}
```

```bash
sudo systemctl reload caddy
```

Caddy obtains and renews the certificate itself. Now only the proxy is reachable from outside, and it asks for a
password. Share the password only with the people who should have it.

## 5. Route A: your machine plus a tunnel

For a demonstration the fastest honest route is to keep running it where it already works and share a temporary link.

1. Start it as usual (`make serve`) and confirm `http://127.0.0.1:8000` works. Run `python scripts/demo_check.py` first, with
   the server stopped.
2. Install a tunnelling tool, for example Cloudflare's `cloudflared`, then:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   It prints a temporary `https://....trycloudflare.com` address that forwards to your server while the command runs.
3. **Add access control before you share it** (the tool's access-policy feature, or a basic-auth proxy as in 4.8). The URL
   alone is unlisted, not secret.
4. Close the tunnel when the demo ends. Your laptop must stay awake, plugged in and online, with the GPU free of other work.

This route was not run here; tunnel tools change, so follow the tool's current documentation.

## 6. Security checklist before anything is public

- [ ] Authentication in front of it (4.8 or a tunnel access policy). The application has none.
- [ ] Port 8000 is bound to `127.0.0.1` and not open in the firewall.
- [ ] `.env` is `chmod 600`, not in git, not in an image or archive; the key is API-restricted and has a quota alert.
- [ ] TLS everywhere outside the machine.
- [ ] Rate limiting at the proxy if the URL is shared widely (each live check spends third-party quota and GPU time).
- [ ] FastAPI's `/docs` and `/openapi.json` are open by default; block them at the proxy if you do not want them public.
- [ ] You are comfortable with the licence limits in section 1 for your use.
- [ ] You have read the limits in [`MODEL_CARD.md`](MODEL_CARD.md) and are not presenting it as an arbiter of truth.

More on the threat model: [`../SECURITY.md`](../SECURITY.md).

## 7. Updating, monitoring and stopping

| Task | How |
| --- | --- |
| Update | `git pull`, then `sudo systemctl restart truthlens`. The page is served with `no-cache`, so browsers pick up changes. If `data/` or `configs/` changed, repackage and unzip the data first. |
| Rebuild the shader bundle | only when `ui-src/` changes; build on any machine with Node and commit the output (`npm run build:rail`). A server needs no Node. |
| Which build is running | `curl localhost:8000/version` (set `TRUTHLENS_GIT_SHA` when there is no `.git`). |
| Health | `curl localhost:8000/health`; `status` is `degraded` if a stage is not loaded. |
| Logs | `journalctl -u truthlens`; traces per request come back from `/verify` with `include_trace`. |
| Rotate the API key | create a new key, edit `.env`, restart; revoke the old one. |
| Stop paying | stop (or delete) the instance. Models and data live on its disk. |
| Back up | the git repository and your `.env`; the runtime archive is rebuildable on the development machine. |

## 8. What is and is not verified

**Verified (2026-10-12, development machine, Windows 11, RTX 4050 Laptop):**

- A clean `git archive` export of the repository plus *only* the 2.1 GB runtime archive, with no `.env`, no `data/private`
  and no other data, starts, reports `status: ok` with all four stages loaded, and answers: the fast-path claim
  (Refuted via a published fact-check), Roman Hindi, Hindi, Gurmukhi, a greeting (not a claim), and live checks (the
  Everest claim Supported from Wikipedia; a Hindi claim Refuted from Wikipedia, since that folder had no fact-check key).
- `serve.py` honours `TRUTHLENS_HOST` and `PORT`; `/version` falls back to `TRUTHLENS_GIT_SHA`.
- The checks the CI runs (lint, tests, leakage and frozen-split guards).

**Not verified:**

- Installation on Linux, and on any cloud provider; the systemd, Caddy and tunnel steps above are standard patterns written
  from general practice, not run here.
- A Docker image. None is provided: a CUDA image is large, could not be built and tested in this environment, and an untested
  image is worse than none. If you build one, base it on an NVIDIA CUDA runtime image, run the same steps as 4.3 and 4.4,
  mount the runtime archive's contents as a volume rather than baking secrets in, and pass the key at run time.
- Behaviour under concurrent users, and long-running stability.
- Mobile browsers on real phones.

## 9. Troubleshooting

See [`OPERATIONS.md`](OPERATIONS.md): CUDA out of memory at start-up, a stale page after an upgrade, port in use,
source throttling, and the tests that cannot run beside a server.
