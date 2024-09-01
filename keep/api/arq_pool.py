from arq import create_pool
from arq.connections import RedisSettings
from keep.api.core.config import config

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