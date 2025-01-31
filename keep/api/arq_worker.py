import logging
from typing import Optional
from uuid import uuid4

from arq import Worker
from arq.connections import RedisSettings
from arq.worker import create_worker
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
    pass


async def shutdown(ctx):
    pass


def get_arq_worker(queue_name: str) -> Worker:
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
    timeout = 30
    functions: list = FUNCTIONS
    queue_name: str
    health_check_interval: int = 10
    health_check_key: str

    def __init__(self, queue_name: str):
        self.queue_name = queue_name
