import os
import time
from importlib import metadata
from typing import Optional

import posthog
import requests
from posthog import Posthog

from keep.api.core.db import get_or_creat_posthog_instance_id  # keep name as-is for compatibility

# --- Version detection (unchanged behavior, just cleaned up) ---
def _get_keep_version() -> str:
    for pkg in ("keep", "keephq"):
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            continue
    return os.environ.get("KEEP_VERSION", "unknown")


KEEP_VERSION = _get_keep_version()

# --- Configuration ---
POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "false").lower() == "true"

# This is apparently a public project key. Still: hardcoding keys in code is how humans get surprised later.
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY") or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://app.posthog.com")

# Timeouts / behavior knobs
POSTHOG_CONNECT_TIMEOUT_SECONDS = float(os.getenv("POSTHOG_CONNECT_TIMEOUT_SECONDS", "3"))
POSTHOG_REACHABILITY_TTL_SECONDS = float(os.getenv("POSTHOG_REACHABILITY_TTL_SECONDS", "30"))
POSTHOG_REACHABILITY_SEND_EVENT = os.getenv("POSTHOG_REACHABILITY_SEND_EVENT", "false").lower() == "true"

# --- Global state (kept, but safer) ---
posthog_client: Optional[Posthog] = None
_reachability_cache: dict[str, float | bool] = {"ts": 0.0, "ok": False}


def _build_posthog_client(*, sync_mode: bool = False, timeout_seconds: Optional[float] = None) -> Posthog:
    """
    Create a Posthog client. No network calls occur here; it just prepares the client.
    """
    return Posthog(
        api_key=POSTHOG_API_KEY,
        host=POSTHOG_HOST,
        feature_flags_request_timeout_seconds=timeout_seconds if timeout_seconds is not None else POSTHOG_CONNECT_TIMEOUT_SECONDS,
        sync_mode=sync_mode,
    )


def get_posthog_client() -> Optional[Posthog]:
    """
    Lazy initializer for PostHog client.
    Returns None if disabled.
    """
    global posthog_client

    if POSTHOG_DISABLED:
        posthog.disabled = True
        return None

    # Initialize once per process.
    if posthog_client is None:
        posthog_client = _build_posthog_client(sync_mode=False)

    return posthog_client


def is_posthog_reachable() -> bool:
    """
    Checks if PostHog is reachable.

    Default behavior:
    - Does NOT send an analytics event (to avoid noise).
    - Uses a lightweight HTTP request to the PostHog host with a short timeout.
    - Caches the result briefly to avoid hammering network/DNS.

    If you *really* want the old behavior (send capture), set:
      POSTHOG_REACHABILITY_SEND_EVENT=true
    """
    now = time.time()
    last_ts = float(_reachability_cache.get("ts", 0.0))
    if now - last_ts < POSTHOG_REACHABILITY_TTL_SECONDS:
        return bool(_reachability_cache.get("ok", False))

    ok = False

    try:
        if POSTHOG_DISABLED:
            ok = False
        elif POSTHOG_REACHABILITY_SEND_EVENT:
            # Old behavior, but guarded and with realistic exception coverage.
            client = _build_posthog_client(sync_mode=True, timeout_seconds=POSTHOG_CONNECT_TIMEOUT_SECONDS)
            distinct_id = get_or_creat_posthog_instance_id()
            client.capture(distinct_id, "connectivity_check")
            ok = True
        else:
            # Lightweight connectivity check: hit the host with a small GET.
            # We’re not relying on a specific endpoint contract here, just network reachability + TLS.
            resp = requests.get(POSTHOG_HOST, timeout=POSTHOG_CONNECT_TIMEOUT_SECONDS)
            ok = resp.status_code < 500
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.SSLError,
        requests.exceptions.ProxyError,
        requests.exceptions.RequestException,
    ):
        ok = False
    except Exception:
        # Don’t let telemetry checks crash app logic.
        ok = False

    _reachability_cache["ts"] = now
    _reachability_cache["ok"] = ok
    return ok