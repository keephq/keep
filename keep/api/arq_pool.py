from arq import create_pool
from keep.api.redis_settings import get_redis_settings

async def get_pool():
    """Create and return an ARQ Redis pool using shared Redis settings."""
    return await create_pool(get_redis_settings())