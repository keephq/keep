import arq.connections as arq_connections

from keep.api.redis_settings import get_redis_settings  # importing applies the patch


async def get_pool():
    return await arq_connections.create_pool(get_redis_settings())