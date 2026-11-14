"""Thin OpenF1 API client for APEX.

Responsibilities:
- Build and send GET requests to OpenF1 endpoints.
- Detect the "live session in progress" lock and raise a clear error.
- Cache every response to disk as Parquet, so we fetch each dataset
  ONCE and reuse it afterwards (no repeated API calls, no rate-limit
  trouble, and work continues while a live session blocks the API).
- Optionally authenticate with a supporter account (raises rate limits
  and allows access during live sessions). Not required for historical
  data outside a live window.

OpenF1 free tier: 3 req/s, 30 req/min. Historical data (outside the
30-min-before to 30-min-after window of a live session) needs no account.
"""

from __future__ import annotations

import time
import hashlib
import json
from pathlib import Path
from typing import Optional

import requests
import pandas as pd

import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))
import config


class LiveSessionLockError(RuntimeError):
    """Raised when OpenF1 returns 401 because a live F1 session is running.

    During a live session the whole API (including past data) is locked
    for unauthenticated users until the session ends. This is temporary,
    not a permanent paywall. Wait for the window to close, or supply a
    supporter account in config.py.
    """


class OpenF1Client:
    def __init__(
        self,
        base_url: str = config.OPENF1_BASE_URL,
        cache_dir: Path = config.CACHE_DIR,
        username: Optional[str] = config.OPENF1_USERNAME,
        password: Optional[str] = config.OPENF1_PASSWORD,
        min_interval_s: float = 0.4,  # stay under 3 req/s
    ):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._min_interval_s = min_interval_s
        self._last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "APEX-F1/0.1 (portfolio project)"})

    # --- Authentication (optional) -----------------------------------------
    def _ensure_token(self) -> Optional[str]:
        """Fetch/refresh an OAuth2 token if credentials are configured."""
        if not (self.username and self.password):
            return None
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        resp = requests.post(
            "https://api.openf1.org/token",
            data={"username": self.username, "password": self.password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + float(data.get("expires_in", 3600))
        return self._token

    # --- Rate limiting -----------------------------------------------------
    def _throttle(self) -> None:
        wait = self._min_interval_s - (time.time() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.time()

    # --- Cache helpers -----------------------------------------------------
    def _cache_path(self, endpoint: str, params: dict) -> Path:
        key = endpoint + "?" + json.dumps(params, sort_keys=True)
        digest = hashlib.md5(key.encode()).hexdigest()[:12]
        safe = endpoint.strip("/").replace("/", "_")
        return self.cache_dir / f"{safe}__{digest}.parquet"

    # --- Core request ------------------------------------------------------
    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        use_cache: bool = True,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """GET an OpenF1 endpoint and return a DataFrame.

        Caches to Parquet. On a cache hit (and refresh=False) no request
        is made. Raises LiveSessionLockError on the live-session 401.
        """
        params = params or {}
        cache_path = self._cache_path(endpoint, params)

        if use_cache and not refresh and cache_path.exists():
            return pd.read_parquet(cache_path)

        self._throttle()
        headers = {}
        token = self._ensure_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{self.base_url}/{endpoint.strip('/')}"
        resp = self.session.get(url, params=params, headers=headers, timeout=60)

        if resp.status_code == 401:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = resp.text[:300]
            raise LiveSessionLockError(
                "OpenF1 returned 401. Most likely a live F1 session is in "
                "progress, which locks the whole API until it ends.\n"
                f"API said: {detail}"
            )
        # 404 means this endpoint has no data for the query (e.g. no laps for a
        # practice session). Treat it as empty, not a crash — callers handle it.
        if resp.status_code == 404:
            return pd.DataFrame()
        resp.raise_for_status()

        try:
            records = resp.json()
        except Exception:
            return pd.DataFrame()
        df = pd.DataFrame(records)

        if use_cache and not df.empty:
            try:
                df.to_parquet(cache_path, index=False)
            except Exception:
                # Some endpoints (e.g. session_result) have mixed-type columns
                # like gap_to_leader ("+1 LAP" vs 5.83). Parquet rejects those.
                # Cast object columns to string and retry; if it still fails,
                # skip caching for this endpoint rather than crash.
                try:
                    safe = df.copy()
                    for c in safe.columns:
                        if safe[c].dtype == object:
                            safe[c] = safe[c].astype(str)
                    safe.to_parquet(cache_path, index=False)
                except Exception:
                    pass
        return df


def is_api_open(client: Optional[OpenF1Client] = None) -> bool:
    """Quick probe: True if historical data is currently reachable."""
    client = client or OpenF1Client()
    try:
        client.get("sessions", {"year": config.TARGET_YEAR}, use_cache=False)
        return True
    except LiveSessionLockError:
        return False
    except Exception:
        return False
