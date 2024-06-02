import asyncio
from httpx import AsyncClient
from arq import create_pool
from arq.connections import RedisSettings
import os

is_keep_arq_provider = os.getenv("IS_KEEP_ARQ_PROVIDER","TRUE")
# The default is to connect to localhost:6379, no password.
REDIS_SETTINGS = RedisSettings()
redis = None

async def init_redis():
    global redis
    redis = await create_pool(REDIS_SETTINGS)

async def handle_event_from_redis(ctx, event):
    print(event)
    pass

async def push_to_redis(event):
    await redis.enqueue_job('handle_event_from_redis', event)
    #print(job.job_id)
    #print(await job.info())
    #print(await job.status())



# WorkerSettings defines the settings to use when creating the work,
# It's used by the arq CLI.
# redis_settings might be omitted here if using the default settings
# For a list of all available settings, see https://arq-docs.helpmanual.io/#arq.worker.Worker
class WorkerSettings:
    functions = [handle_event_from_redis]
    #on_startup = startup
    #on_shutdown = shutdown
    redis_settings = REDIS_SETTINGS