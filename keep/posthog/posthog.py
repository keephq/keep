import os
import time
import uuid
import posthog
import logging
import requests

from importlib import metadata
from posthog import Posthog

logger = logging.getLogger(__name__)

DISABLE_POSTHOG = os.getenv("DISABLE_POSTHOG", "false") == "true"
UPTIME_REPORTING_CADENCE = 60 * 10
RANDOM_TENANT_ID_PERSISTENT_WITHIN_LAUNCH = uuid.uuid4()

if DISABLE_POSTHOG:
    posthog.disabled = True

try:
    KEEP_VERSION = metadata.version("keep")
except Exception:
    KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")

def get_posthog_client(sync_mode=False):
    posthog_api_key = (
        os.getenv("POSTHOG_API_KEY")
        or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"
    )
    posthog_client = Posthog(api_key=posthog_api_key, host="https://app.posthog.com", sync_mode=sync_mode)
    return posthog_client

def is_posthog_reachable():
    posthog_client = get_posthog_client(sync_mode=True)
    try:
        posthog_client.capture(
            RANDOM_TENANT_ID_PERSISTENT_WITHIN_LAUNCH, 
            "connectivity_check",
        )
        return True
    except requests.exceptions.ConnectionError:
        return False

def report_uptime_to_posthog_blocking():
    while True:
        posthog_client = get_posthog_client()
        posthog_client.capture(
            RANDOM_TENANT_ID_PERSISTENT_WITHIN_LAUNCH,
            "backend_status",
            properties={
                "status": "up",
                "keep_version": KEEP_VERSION,
            },
        )
        logger.info("Uptime reported to PostHog.")
        time.sleep(UPTIME_REPORTING_CADENCE)
