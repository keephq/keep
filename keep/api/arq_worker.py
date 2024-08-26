import os
import logging
from typing import Optional

from arq import Worker, create_pool, cron
from arq.connections import RedisSettings
from arq.worker import create_worker
from pydantic.utils import import_string
from starlette.datastructures import CommaSeparatedStrings

import keep.api.logging
from keep.api.core.config import config
from keep.api.tasks.process_background_ai_task import process_background_ai_task
from keep.api.tasks.healthcheck_task import healthcheck_task

keep.api.logging.setup_logging()
logger = logging.getLogger(__name__)

###
# Set ARQ_TASK_POOL_TO_EXECUTE to "none", "all", "basic_processing" or "ai" 
# to split the tasks between the workers.
###

ARQ_TASK_POOL_TO_EXECUTE_NONE = "none"  # Arq workers explicitly disabled for this service
ARQ_TASK_POOL_TO_EXECUTE_ALL = "all"  # All arq workers enabled for this service
ARQ_TASK_POOL_TO_EXECUTE_BASIC_PROCESSING = "basic_processing" # Everything except AI
ARQ_TASK_POOL_TO_EXECUTE_AI = "ai" # Only AI

REDIS = os.environ.get("REDIS", "false") == "true"
ARQ_TASK_POOL_TO_EXECUTE = os.environ.get("ARQ_TASK_POOL_TO_EXECUTE", None)

# Backwards compatible. If REDIS is enabled and ARQ_WORKERS is not set, default to "all".
if REDIS and ARQ_TASK_POOL_TO_EXECUTE is None:
    ARQ_TASK_POOL_TO_EXECUTE = ARQ_TASK_POOL_TO_EXECUTE_ALL

# If REDIS is disabled and ARQ_WORKERS is not set, default to "none".
if REDIS is None and ARQ_TASK_POOL_TO_EXECUTE is None:
    ARQ_TASK_POOL_TO_EXECUTE = ARQ_TASK_POOL_TO_EXECUTE_NONE

if ARQ_TASK_POOL_TO_EXECUTE != ARQ_TASK_POOL_TO_EXECUTE_NONE and not REDIS:
    logger.critical("Starting the ARQ worker, but REDIS is not enabled. Most likely the worker will not work.")

# Current worker will pick up tasks only according to it's execution pool:
all_tasks_for_the_worker = ["keep.api.tasks.healthcheck_task.healthcheck_task"]

if ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_ALL or \
    ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_BASIC_PROCESSING:
    all_tasks_for_the_worker += [
        "keep.api.tasks.process_event_task.async_process_event",
        "keep.api.tasks.process_topology_task.async_process_topology",
    ]

if ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_ALL or \
    ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_AI:
    all_tasks_for_the_worker += [
        "keep.api.tasks.process_background_ai_task.process_background_ai_task",
        "keep.api.tasks.process_background_ai_task.process_correlation",
    ]

ARQ_BACKGROUND_FUNCTIONS: Optional[CommaSeparatedStrings] = config(
    "ARQ_BACKGROUND_FUNCTIONS",
    cast=CommaSeparatedStrings,
    default=all_tasks_for_the_worker,
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
    pass


async def shutdown(ctx):
    pass


async def get_pool():
    return await create_pool(
        RedisSettings(
            host=config("REDIS_HOST", default="localhost"),
            port=config("REDIS_PORT", cast=int, default=6379),
            username=config("REDIS_USERNAME", default=None),
            password=config("REDIS_PASSWORD", default=None),
            conn_timeout=60,
            conn_retries=10,
        )
    )

def get_arq_worker() -> Worker:
    keep_result = config(
        "ARQ_KEEP_RESULT", cast=int, default=3600
    )  # duration to keep job results for
    expires = config(
        "ARQ_EXPIRES", cast=int, default=3600
    )  # the default length of time from when a job is expected to start after which the job expires, making it shorter to avoid clogging
    return create_worker(
        WorkerSettings, keep_result=keep_result, expires_extra_ms=expires
    )

def at_every_x_minutes(x: int, start: int = 0, end: int = 59):
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
    # Only if it's an AI-dedicated worker, we can set large timeout, otherwise keeping low to avoid clogging
    timeout = 60 * 15 if ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_AI else 30
    functions: list = FUNCTIONS
    cron_jobs = [
        cron(
            healthcheck_task,
            minute=at_every_x_minutes(1),
            unique=True,
            timeout=30, 
            max_tries=1, 
            run_at_startup=True,
        ),
    ]
    if ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_ALL or \
        ARQ_TASK_POOL_TO_EXECUTE == ARQ_TASK_POOL_TO_EXECUTE_AI:
        cron_jobs.append(
            cron(
                process_background_ai_task,
                minute=at_every_x_minutes(1),
                unique=True,
                timeout=30, 
                max_tries=1, 
                run_at_startup=True,
            )
        )
