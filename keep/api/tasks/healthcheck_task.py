import logging

logger = logging.getLogger(__name__)


async def healthcheck_task(*args, **kwargs):
    logger.info("Healthcheck task ran. Just indicating that the background worker is running.")
