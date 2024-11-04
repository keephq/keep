import asyncio
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
UPTIME_REPORTING_CADENCE = 60 * 60  # 1 hour

async def report_uptime_to_posthog():
    """
    Reports uptime and current version to PostHog every hour.
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
         # Important to keep it async, otherwise will clog main gunicorn thread and cause timeouts.
        await asyncio.sleep(UPTIME_REPORTING_CADENCE)

def launch_uptime_reporting():
    """
    Running async uptime reporting as a sub-thread.
    """
    if not POSTHOG_DISABLED:
        if is_posthog_reachable():
            thread = threading.Thread(target=asyncio.run, args=(report_uptime_to_posthog(), ))
            thread.start()
            logger.info("Uptime Reporting to Posthog launched.")
        else:
            logger.info("Reporting to Posthog not launched because it's not reachable.")
    else:
        logger.info("Posthog reporting is disabled so no uptime reporting.")
