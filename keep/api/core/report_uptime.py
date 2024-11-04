import time
import logging
import threading
from keep.api.core.posthog import (
    posthog_client,
    is_posthog_reachable,
    KEEP_VERSION, 
    POSTHOG_DISABLED, 
    RANDOM_TENANT_ID_PERSISTENT_WITHIN_LAUNCH
)

logger = logging.getLogger(__name__)
UPTIME_REPORTING_CADENCE = 5

def report_uptime_to_posthog_blocking():
    """
    It's a blocking function that reports uptime and current version to PostHog every hour.
    Should be lunched in a separate thread.
    """
    while True:
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

def launch_uptime_reporting():
    """
    Running uptime reporting as a sub-thread. Important to avoid 
    Launching at app.on_start() caused misterious isses on production, see:
    Check: https://github.com/keephq/keep/pull/2366
    Reverted: https://github.com/keephq/keep/pull/2384
    """
    if not POSTHOG_DISABLED:
        if is_posthog_reachable():
            thread = threading.Thread(target=report_uptime_to_posthog_blocking)
            thread.start()
            logger.info("Uptime Reporting to Posthog launched.")
        else:
            logger.info("Reporting to Posthog not launched because it's not reachable.")
    else:
        logger.info("Posthog reporting is disabled so no uptime reporting.")
