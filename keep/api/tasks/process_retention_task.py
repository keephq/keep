import asyncio
import datetime
import logging

import redis
from filelock import FileLock, Timeout

from keep.api.consts import (
    KEEP_ALERT_RETENTION_BATCH_SIZE,
    KEEP_ALERT_RETENTION_DAYS,
    KEEP_ALERT_RETENTION_INTERVAL,
    REDIS,
)
from keep.api.core.db import delete_alerts_by_retention, get_tenants

logger = logging.getLogger(__name__)


def process_retention(logger):
    if KEEP_ALERT_RETENTION_DAYS <= 0:
        return
    purge_before = datetime.datetime.utcnow() - datetime.timedelta(
        days=KEEP_ALERT_RETENTION_DAYS
    )
    for tenant in get_tenants():
        deleted = delete_alerts_by_retention(
            tenant.id, purge_before, KEEP_ALERT_RETENTION_BATCH_SIZE
        )
        if deleted:
            logger.info(
                "Deleted alerts by retention policy",
                extra={"tenant_id": tenant.id, "deleted": deleted},
            )


async def async_process_retention(*args):
    if REDIS:
        ctx = args[0]
        redis_instance: redis.Redis = ctx.get("redis")
        lock_key = "lock:retention:process"
        lock_acquired = await redis_instance.set(lock_key, "1", ex=3600, nx=True)
        if not lock_acquired:
            logger.info("Retention process is already running, skipping this run.")
            return
        logger.info("Retention process started, acquiring lock.")
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(ctx.get("pool"), process_retention, logger)
        except Exception as e:
            logger.error("Error in retention process: %s", e, exc_info=True)
            raise
        finally:
            await redis_instance.delete(lock_key)
            logger.info("Retention process completed and lock released.")
    else:
        while True:
            init_time = datetime.datetime.now()
            try:
                with FileLock(
                    "/tmp/retention_process.lock",
                    timeout=KEEP_ALERT_RETENTION_INTERVAL // 2,
                ):
                    logger.info("Retention process started, acquiring lock.")
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, process_retention, logger)
                    complete_time = datetime.datetime.now()
                    await asyncio.sleep(
                        max(
                            0,
                            KEEP_ALERT_RETENTION_INTERVAL
                            - (complete_time - init_time).total_seconds(),
                        )
                    )
                    logger.info("Retention process completed.")
            except Timeout:
                logger.info("Retention process is already running, skipping this run.")
