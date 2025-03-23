import asyncio
import logging
import multiprocessing
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
    KEEP_ARQ_TASK_POOL_NONE,
)
from keep.api.core.config import config
from keep.api.core.db import dispose_session

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


async def startup(ctx):
    """ARQ worker startup callback"""
    pass


async def shutdown(ctx):
    """ARQ worker shutdown callback"""
    pass


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


async def safe_run_worker(worker: Worker):
    """
    Run a worker with automatic reconnection in case of Redis connection errors.

    Args:
        worker: The ARQ worker to run
    """
    try:
        while True:
            try:
                await worker.async_run()
            except asyncio.CancelledError:  # pragma: no cover
                # happens on shutdown, fine
                pass
            except redis.exceptions.ConnectionError:
                logger.exception("Failed to connect to Redis... Retry in 3 seconds")
                await asyncio.sleep(3)
                continue
            break
    finally:
        await worker.close()


async def start_worker_instance(queue_name: str, worker_index: int):
    """
    Start a single worker instance.

    Args:
        queue_name: The queue to listen to
        worker_index: Index of this worker for logging purposes
    """
    logger.info(f"Starting worker {worker_index} for queue {queue_name}")
    worker = get_arq_worker(queue_name)
    await safe_run_worker(worker)


def run_worker_process(queue_name: str, worker_index: int):
    """
    Run a worker in a separate process.

    Args:
        queue_name: The queue to listen to
        worker_index: Index of this worker for logging purposes
    """
    logger.info(f"Worker process {worker_index} starting")
    dispose_session()  # Dispose any existing DB connections in the child process
    asyncio.run(start_worker_instance(queue_name, worker_index))


async def start_workers():
    """
    Start the ARQ workers based on configuration with multi-process support.
    """
    logger.info("Disposing existing DB connections")
    dispose_session()

    if KEEP_ARQ_TASK_POOL == KEEP_ARQ_TASK_POOL_NONE:
        logger.info("No task pools configured to run")
        return

    try:
        # Get the number of worker processes to spawn from environment variable
        worker_count = config("KEEP_WORKERS", cast=int, default=1)
        logger.info(
            f"Starting {worker_count} worker processes with task pool: {KEEP_ARQ_TASK_POOL}"
        )

        processes = []

        if KEEP_ARQ_TASK_POOL == KEEP_ARQ_TASK_POOL_ALL:
            logger.info("Starting all task pools")

            # Spawn worker processes for basic queue
            for i in range(worker_count):
                logger.info(f"Starting worker process {i}")
                process = multiprocessing.Process(
                    target=run_worker_process,
                    args=(KEEP_ARQ_QUEUE_BASIC, i),
                    daemon=True,
                )
                process.start()
                processes.append(process)
                logger.info(f"Worker process {i} started")

        elif KEEP_ARQ_TASK_POOL == KEEP_ARQ_TASK_POOL_BASIC_PROCESSING:
            logger.info("Starting Basic Processing task pool")

            # Spawn worker processes for basic queue
            for i in range(worker_count):
                logger.info(f"Starting worker process {i}")
                process = multiprocessing.Process(
                    target=run_worker_process,
                    args=(KEEP_ARQ_QUEUE_BASIC, i),
                    daemon=True,
                )
                process.start()
                processes.append(process)
                logger.info(f"Worker process {i} started")

        else:
            raise ValueError(f"Invalid task pool: {KEEP_ARQ_TASK_POOL}")

        # Wait for all processes to complete
        for process in processes:
            process.join()

    except Exception as e:
        logger.exception(f"Failed to start ARQ workers: {e}")
        raise


async def run_workers():
    """
    Main entry point for running workers with error handling.
    """
    try:
        logger.info("Starting Workers")
        await start_workers()
        logger.info("Workers finished")
    except KeyboardInterrupt:
        logger.info("Workers shutting down due to keyboard interrupt")
    except Exception as e:
        logger.exception(f"Workers failed with exception: {e}")
        raise


if __name__ == "__main__":
    logger.info(f"Starting ARQ workers with task pool: {KEEP_ARQ_TASK_POOL}")
    worker_count = config("KEEP_WORKERS", cast=int, default=1)
    logger.info(f"Worker process count: {worker_count}")
    asyncio.run(run_workers())
