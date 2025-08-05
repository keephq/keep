import asyncio
import datetime
import logging
from filelock import FileLock, Timeout
import redis
from keep.api.bl.maintenance_windows_bl import MaintenanceWindowsBl
from keep.api.consts import REDIS, WATCHER_LAPSED_TIME

logger = logging.getLogger(__name__)


async def async_process_watcher(*args):
    if REDIS:
        ctx = args[0]
        redis_instance: redis.Redis = ctx.get("redis")
        lock_key = "lock:watcher:process"
        is_exec_stopped = await redis_instance.set(lock_key, "1", ex=WATCHER_LAPSED_TIME+10, nx=True)
        if not is_exec_stopped:
            logger.info("Watcher process is already running, skipping this run.")
            return
        logger.info("Watcher process started, acquiring lock.")
        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(ctx.get("pool"), MaintenanceWindowsBl.recover_strategy, logger)
        except Exception as e:
            logger.error("Error in run_in_executor: %s", e, exc_info=True)
            raise
        finally:
            await redis_instance.delete(lock_key)
            logger.info("Watcher process completed and lock released.")
        return resp
    else:
        while True:
            init_time = datetime.datetime.now()
            try:
                with FileLock("/tmp/watcher_process.lock", timeout=WATCHER_LAPSED_TIME//2):
                    logger.info("Watcher process started, acquiring lock.")
                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(None, MaintenanceWindowsBl.recover_strategy, logger)
                    logger.info("Sleeping for 60 seconds before next run.")
                    complete_time = datetime.datetime.now()
                    await asyncio.sleep(WATCHER_LAPSED_TIME - (complete_time - init_time).total_seconds())
                    logger.info("Unlock process completed.")
            except Timeout:
                logger.info("Watcher process is already running, skipping this run.")