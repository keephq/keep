import os
import time
import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from keep.api.core.db import get_activity_report, get_or_creat_posthog_instance_id
from keep.api.core.posthog import (
    posthog_client,
    is_posthog_reachable,
    KEEP_VERSION,
    POSTHOG_DISABLED,
)

logger = logging.getLogger(__name__)

UPTIME_REPORTING_CADENCE_SEC = 60 * 60  # 1 hour
ACTIVITY_REPORT_TIMEOUT_SEC = 5.0       # keep this small; it's "insurance", not core service

LAUNCH_TIME_UTC = datetime.now(timezone.utc)

# Prevent accidental double-launch (reloads, repeated init, etc.)
_uptime_thread_lock = threading.Lock()
_uptime_thread: Optional[threading.Thread] = None


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


async def _safe_activity_report() -> dict:
    """
    get_activity_report() is assumed sync and may touch the DB.
    Run it in a worker thread with a timeout so uptime reporting doesn't hang forever.
    """
    try:
        # Offload sync DB/report work so this coroutine can timeout cleanly.
        return await asyncio.wait_for(
            asyncio.to_thread(get_activity_report),
            timeout=ACTIVITY_REPORT_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.warning("get_activity_report() timed out after %.1fs", ACTIVITY_REPORT_TIMEOUT_SEC)
        return {"activity_report_timeout": True}
    except Exception:
        logger.exception("get_activity_report() failed")
        return {"activity_report_error": True}


async def report_uptime_to_posthog() -> None:
    """
    Reports uptime and current version to PostHog every hour.
    Intended to run in a dedicated background thread via asyncio.run().
    """
    ee_enabled = _env_bool("EE_ENABLED", default=False)
    api_url = os.environ.get("KEEP_API_URL") if ee_enabled else None

    while True:
        try:
            start = time.monotonic()

            properties = {
                "status": "up",
                "keep_version": KEEP_VERSION,
            }

            # Pull the DB activity report safely
            properties.update(await _safe_activity_report())

            # Timing + uptime (UTC)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            properties["db_request_duration_ms"] = elapsed_ms
            properties["uptime_hours"] = round(
                (datetime.now(timezone.utc) - LAUNCH_TIME_UTC).total_seconds() / 3600,
                2,
            )

            if api_url:
                properties["api_url"] = api_url

            # PostHog
            distinct_id = get_or_creat_posthog_instance_id()  # keep upstream name; don't break imports
            posthog_client.capture(distinct_id, "backend_status", properties=properties)
            posthog_client.flush()

            # Logging: keep message stable; extras are optional and may not render in all formatters
            logger.info("Uptime reported to PostHog.", extra={"properties": properties})

        except Exception:
            # Never allow the loop to die silently
            logger.exception("Uptime reporting loop crashed; continuing after sleep")

        await asyncio.sleep(UPTIME_REPORTING_CADENCE_SEC)


def launch_uptime_reporting_thread() -> Optional[threading.Thread]:
    """
    Launch async uptime reporting in a daemon background thread.
    Returns the thread if started; otherwise returns None.
    """
    if POSTHOG_DISABLED:
        logger.info("PostHog reporting is disabled; uptime reporting not started.")
        return None

    if not is_posthog_reachable():
        logger.info("PostHog not reachable; uptime reporting not started.")
        return None

    global _uptime_thread

    with _uptime_thread_lock:
        # If already started and alive, don't start a second loop.
        if _uptime_thread is not None and _uptime_thread.is_alive():
            logger.info("Uptime reporting thread already running; not starting another.")
            return _uptime_thread

        thread = threading.Thread(
            target=asyncio.run,
            args=(report_uptime_to_posthog(),),
            daemon=True,
            name="keep-uptime-reporting",
        )
        thread.start()
        _uptime_thread = thread

    logger.info("Uptime reporting to PostHog launched.")
    return _uptime_thread