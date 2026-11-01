from __future__ import annotations

import hashlib
import json as _json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)
UA = "scout/0.1 (+https://github.com/; daily paper reading practice)"


def _cache_dir() -> Path:
    d = Path(os.environ.get("SCOUT_CACHE_DIR", "data/cache")) / "http"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(url: str, params: dict | None) -> str:
    return hashlib.sha1(_json.dumps([url, params or {}], sort_keys=True).encode()).hexdigest()


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        retries: int = 4, timeout: float = 30.0, json: bool = True, cache_hours: float = 0) -> Any | None:
    """GET with exponential backoff and an optional on-disk cache. Returns parsed JSON (or text) or None."""
    cpath = _cache_dir() / f"{_cache_key(url, params)}.json" if cache_hours else None
    if cpath and cpath.exists() and (time.time() - cpath.stat().st_mtime) < cache_hours * 3600:
        try:
            return _json.loads(cpath.read_text())["v"]
        except (ValueError, KeyError):
            pass
    h = {"User-Agent": UA, **(headers or {})}
    delay = 3.0
    for attempt in range(retries):
        try:
            r = httpx.get(url, params=params, headers=h, timeout=timeout, follow_redirects=True)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            val = r.json() if json else r.text
            if cpath:
                cpath.write_text(_json.dumps({"v": val}))
            return val
        except (httpx.HTTPError, ValueError) as e:
            if attempt == retries - 1:
                log.warning("GET %s failed after %d tries: %s", url, retries, e)
                return None
            time.sleep(delay)
            delay *= 2
    return None


def post(url: str, *, body: dict, params: dict | None = None, headers: dict | None = None,
         retries: int = 3, timeout: float = 30.0) -> Any | None:
    h = {"User-Agent": UA, **(headers or {})}
    delay = 1.5
    for attempt in range(retries):
        try:
            r = httpx.post(url, json=body, params=params, headers=h, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            if attempt == retries - 1:
                log.warning("POST %s failed after %d tries: %s", url, retries, e)
                return None
            time.sleep(delay)
            delay *= 2
    return None
