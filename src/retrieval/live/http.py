"""A polite JSON-over-HTTP getter, with a disk cache.

Why this exists as its own module: the spike that preceded it was rate-limited
by Wikipedia (HTTP 429) after about fifty requests in a minute, and a demo that
dies on the first burst is worse than one that is a second slower. So:

- **throttle**: a minimum gap between requests to the same host;
- **backoff**: 429 and 5xx are retried, honouring `Retry-After`;
- **timeout**: one budget for the whole call, so a slow API degrades the card to
  its offline answer instead of hanging the request (NFR-7);
- **cache**: every successful response is stored on disk under a hash of the
  full URL. A repeated demo is instant and gives identical answers, and a test
  can replay a recording with no network at all.

The key is part of the URL Google needs, so the cache key and every log line use
`redact(url)`: the key never reaches disk, a log or a trace.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common.hashing import sha256_obj

CACHE_DIR = Path("data/interim/live_cache")        # gitignored, like all of data/interim
USER_AGENT = "TruthLens/0.1 (CSE472 student project; claim verification research)"
_KEY = re.compile(r"([?&](?:key|api_key)=)[^&]+", re.IGNORECASE)


class LiveError(RuntimeError):
    """A live source failed. Callers degrade to the offline answer."""


def redact(url: str) -> str:
    """The URL with any API key removed -- safe to cache under, log and trace."""
    return _KEY.sub(r"\1***", url)


class Fetcher:
    """GET -> parsed JSON, throttled, retried, cached."""

    def __init__(self, cache_dir: Path | str = CACHE_DIR, min_gap_s: float = 0.35,
                 timeout_s: float = 4.0, retries: int = 2, use_cache: bool = True,
                 opener: Callable[[urllib.request.Request, float], Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.cache_dir = Path(cache_dir)
        self.min_gap_s = min_gap_s
        self.timeout_s = timeout_s
        self.retries = retries
        self.use_cache = use_cache
        self._opener = opener or (lambda req, timeout: urllib.request.urlopen(req, timeout=timeout))
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}

    # -- cache ---------------------------------------------------------------
    def _path(self, url: str) -> Path:
        return self.cache_dir / f"{sha256_obj(redact(url))[:32]}.json"

    def cached(self, url: str) -> Any | None:
        path = self._path(url)
        if self.use_cache and path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))["body"]
        return None

    def _store(self, url: str, body: Any) -> None:
        path = self._path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"url": redact(url), "body": body}, ensure_ascii=False),
                        encoding="utf-8")

    # -- network -------------------------------------------------------------
    def _throttle(self, host: str) -> None:
        wait = self._last.get(host, float("-inf")) + self.min_gap_s - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last[host] = self._clock()

    def get_json(self, url: str) -> Any:
        if (hit := self.cached(url)) is not None:
            return hit
        host = urllib.parse.urlparse(url).netloc
        started = self._clock()
        last_error = "no attempt"
        for attempt in range(self.retries + 1):
            if self._clock() - started > self.timeout_s * (self.retries + 1):
                break
            self._throttle(host)
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with self._opener(request, self.timeout_s) as response:
                    body = json.load(response)
                self._store(url, body)
                return body
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code == 429 or exc.code >= 500:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    self._sleep(min(float(retry_after), 5.0) if retry_after and retry_after.isdigit()
                                else 1.5 * (attempt + 1))
                    continue
                break                                # 4xx other than 429: retrying cannot help
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last_error = type(exc).__name__
                self._sleep(0.5 * (attempt + 1))
        raise LiveError(f"{redact(url)[:90]}: {last_error}")
