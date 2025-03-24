import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from uuid import uuid4

import redis
from arq import Worker
from arq.connections import RedisSettings
from arq.worker import create_worker
from dotenv import find_dotenv, load_dotenv
from pydantic.utils import import_string
from starlette.datastructures import CommaSeparatedStrings

import keep.api.logging
from keep.api.consts import (
    KEEP_ARQ_QUEUE_BASIC,
    KEEP_ARQ_TASK_POOL,
    KEEP_ARQ_TASK_POOL_ALL,
    KEEP_ARQ_TASK_POOL_BASIC_PROCESSING,
)
from keep.api.core.config import config
from keep.api.tasks.process_event_task import process_event

# Load environment variables
load_dotenv(find_dotenv())
keep.api.logging.setup_logging()
logger = logging.getLogger(__name__)

# Current worker will pick up tasks only according to its execution pool:
all_tasks_for_the_worker = []

if KEEP_ARQ_TASK_POOL in [KEEP_ARQ_TASK_POOL_ALL, KEEP_ARQ_TASK_POOL_BASIC_PROCESSING]:
    all_tasks_for_the_worker += [
        ("keep.api.tasks.process_event_task.async_process_event", KEEP_ARQ_QUEUE_BASIC),
        (
            "keep.api.tasks.process_topology_task.async_process_topology",
            KEEP_ARQ_QUEUE_BASIC,
        ),
        (
            "keep.api.tasks.process_incident_task.async_process_incident",
            KEEP_ARQ_QUEUE_BASIC,
        ),
    ]


ARQ_BACKGROUND_FUNCTIONS: Optional[CommaSeparatedStrings] = config(
    "ARQ_BACKGROUND_FUNCTIONS",
    cast=CommaSeparatedStrings,
    default=[task for task, _ in all_tasks_for_the_worker],
)

FUNCTIONS: list = (
    [
        import_string(background_function)
        for background_function in list(ARQ_BACKGROUND_FUNCTIONS)
    ]
    if ARQ_BACKGROUND_FUNCTIONS is not None
    else list()
)


async def process_event_in_worker(
    ctx,
    tenant_id,
    provider_type,
    provider_id,
    fingerprint,
    api_key_name,
    trace_id,
    event,
    notify_client=True,
    timestamp_forced=None,
):
    logger.info(
        "Processing event in worker",
        extra={
            "tenant_id": tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
            "fingerprint": fingerprint,
            "tract_id": trace_id,
        },
    )
    # Create a new context that includes both the arq ctx and any other parameters
    process_event_func_sync = functools.partial(
        process_event,
        ctx=ctx,  # Pass ctx as a named parameter
        tenant_id=tenant_id,
        provider_type=provider_type,
        provider_id=provider_id,
        fingerprint=fingerprint,
        api_key_name=api_key_name,
        trace_id=trace_id,
        event=event,
        notify_client=notify_client,
        timestamp_forced=timestamp_forced,
    )
    loop = asyncio.get_running_loop()
    # run the function in the thread pool
    resp = await loop.run_in_executor(ctx["pool"], process_event_func_sync)
    logger.info(
        "Event processed in worker",
        extra={
            "tenant_id": tenant_id,
            "provider_type": provider_type,
            "provider_id": provider_id,
            "fingerprint": fingerprint,
            "tract_id": trace_id,
        },
    )
    return resp


FUNCTIONS.append(process_event_in_worker)


async def startup(ctx):
    """ARQ worker startup callback"""
    EVENT_WORKERS = int(config("KEEP_EVENT_WORKERS", default=5, cast=int))
    # Create dedicated threadpool
    process_event_executor = ThreadPoolExecutor(
        max_workers=EVENT_WORKERS, thread_name_prefix="process_event_worker"
    )
    ctx["pool"] = process_event_executor


async def shutdown(ctx):
    """ARQ worker shutdown callback"""
    # Clean up any resources if needed
    if "pool" in ctx:
        ctx["pool"].shutdown(wait=True)


def at_every_x_minutes(x: int, start: int = 0, end: int = 59):
    """Helper function to generate cron-like minute intervals"""
    return {*list(range(start, end, x))}


class WorkerSettings:
    """
    Settings for the ARQ worker.
    """

    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=config("REDIS_HOST", default="localhost"),
        port=config("REDIS_PORT", cast=int, default=6379),
        username=config("REDIS_USERNAME", default=None),
        password=config("REDIS_PASSWORD", default=None),
        conn_timeout=60,
        conn_retries=10,
        conn_retry_delay=10,
    )
    timeout = 30
    functions: list = FUNCTIONS
    queue_name: str
    health_check_interval: int = 10
    health_check_key: str

    def __init__(self, queue_name: str):
        self.queue_name = queue_name


def get_arq_worker(queue_name: str) -> Worker:
    """
    Create and configure an ARQ worker for the specified queue.

    Args:
        queue_name: The name of the queue to which the worker will listen

    Returns:
        A configured ARQ worker
    """
    keep_result = config(
        "ARQ_KEEP_RESULT", cast=int, default=3600
    )  # duration to keep job results for
    expires = config(
        "ARQ_EXPIRES", cast=int, default=3600
    )  # the default length of time from when a job is expected to start after which the job expires, making it shorter to avoid clogging

    # generate a worker id so each worker will have a different health check key
    worker_id = str(uuid4()).replace("-", "")
    worker = create_worker(
        WorkerSettings,
        keep_result=keep_result,
        expires_extra_ms=expires,
        queue_name=queue_name,
        health_check_key=f"{queue_name}:{worker_id}:health-check",
    )
    return worker


async def safe_run_worker(worker: Worker, number_of_errors_before_restart=0):
    """
    Run a worker with automatic reconnection in case of Redis connection errors.

    Args:
        worker: The ARQ worker to run
    """
    try:
        number_of_errors = 0
        while True:
            try:
                await worker.async_run()
            except asyncio.CancelledError:  # pragma: no cover
                # happens on shutdown, fine
                pass
            except redis.exceptions.ConnectionError:
                number_of_errors += 1
                # we want to raise an exception if we have too many errors
                if (
                    number_of_errors_before_restart
                    and number_of_errors >= number_of_errors_before_restart
                ):
                    logger.error(
                        f"Worker encountered {number_of_errors} errors, restarting..."
                    )
                    raise
                logger.exception("Failed to connect to Redis... Retry in 3 seconds")
                await asyncio.sleep(3)
                continue
            except Exception:
                number_of_errors += 1
                # we want to raise an exception if we have too many errors
                if (
                    number_of_errors_before_restart
                    and number_of_errors >= number_of_errors_before_restart
                ):
                    logger.error(
                        f"Worker encountered {number_of_errors} errors, restarting..."
                    )
                    raise
                # o.w: log the error and continue
                logger.exception("Worker error")
                await asyncio.sleep(3)
                continue

            break
    finally:
        await worker.close()
