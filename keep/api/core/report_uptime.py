import asyncio
import logging
import threading
from keep.api.core.db import get_activity_report, get_or_creat_posthog_instance_id
from keep.api.core.posthog import (
    posthog_client,
    is_posthog_reachable,
    KEEP_VERSION, 
    POSTHOG_DISABLED, 
)

logger = logging.getLogger(__name__)
UPTIME_REPORTING_CADENCE = 60 * 60  # 1 hour

async def report_uptime_to_posthog():
    """
    Reports uptime and current version to PostHog every hour.
    Should be lunched in a separate thread.
    """
    while True:
        start_time = asyncio.get_event_loop().time()
        properties = {
            "status": "up",
            "keep_version": KEEP_VERSION,
            **get_activity_report(),
        }
        end_time = asyncio.get_event_loop().time()
        properties["db_request_duration_ms"] = int((end_time - start_time) * 1000)
        posthog_client.capture(
            get_or_creat_posthog_instance_id(),
            "backend_status",
            properties=properties,
        )
        posthog_client.flush()
        logger.info("Uptime reported to PostHog.")

        await asyncio.sleep(UPTIME_REPORTING_CADENCE)

def launch_uptime_reporting_thread() -> threading.Thread | None:
    """
    Running async uptime reporting as a sub-thread.
    """
    if not POSTHOG_DISABLED:
        if is_posthog_reachable():
            thread = threading.Thread(target=asyncio.run, args=(report_uptime_to_posthog(), ))
            thread.start()
            logger.info("Uptime Reporting to Posthog launched.")
            return thread
        else:
            logger.info("Reporting to Posthog not launched because it's not reachable.")
    else:
        logger.info("Posthog reporting is disabled so no uptime reporting.")
