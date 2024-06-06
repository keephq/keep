# builtins
from typing import Optional

# third-party
from arq import Worker
from arq.connections import RedisSettings
from arq.worker import create_worker
from pydantic.utils import import_string
from starlette.datastructures import CommaSeparatedStrings

# internals
from keep.api.core.config import config

ARQ_BACKGROUND_FUNCTIONS: Optional[CommaSeparatedStrings] = config(
    "ARQ_BACKGROUND_FUNCTIONS",
    cast=CommaSeparatedStrings,
    default=["keep.api.tasks.event_handler.process_event"],
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


def get_worker() -> Worker:
    keep_result = config(
        "ARQ_KEEP_RESULT", cast=int, default=3600
    )  # duration to keep job results for
    expires = config(
        "ARQ_EXPIRES", cast=int, default=86_400_000
    )  # the default length of time from when a job is expected to start after which the job expires, defaults to 1 day in ms
    return create_worker(
        WorkerSettings, keep_result=keep_result, expires_extra_ms=expires
    )


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
        conn_retries=10,
        conn_retry_delay=10,
    )
    functions: list = FUNCTIONS
