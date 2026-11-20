"""
Shared Redis configuration module for ARQ pool and worker.

This module provides a centralized way to configure Redis connections,
supporting both direct Redis and Redis Sentinel configurations.
"""

import arq.connections
from arq.connections import RedisSettings
from redis.asyncio.sentinel import Sentinel as _OrigSentinel

from keep.api.core.config import config


class _AuthenticatedSentinel(_OrigSentinel):
    """
    Subclass of redis.asyncio.sentinel.Sentinel ensuring credentials are forwarded
    to Sentinel discovery nodes (port 26379) via sentinel_kwargs, resolving issue #6886.
    """

    def __init__(
        self,
        sentinels,
        min_other_sentinels=0,
        sentinel_kwargs=None,
        **connection_kwargs,
    ):
        if sentinel_kwargs is None:
            sentinel_kwargs = {
                k: v for k, v in connection_kwargs.items() if k.startswith("socket_")
            }
            if "password" in connection_kwargs and connection_kwargs["password"]:
                sentinel_kwargs["password"] = connection_kwargs["password"]
            if "username" in connection_kwargs and connection_kwargs["username"]:
                sentinel_kwargs["username"] = connection_kwargs["username"]
        elif (
            "password" in connection_kwargs
            and "password" not in sentinel_kwargs
            and connection_kwargs["password"]
        ):
            sentinel_kwargs["password"] = connection_kwargs["password"]

        super().__init__(
            sentinels,
            min_other_sentinels=min_other_sentinels,
            sentinel_kwargs=sentinel_kwargs,
            **connection_kwargs,
        )


def _patch_arq_sentinel():
    """Ensure arq.connections.Sentinel uses _AuthenticatedSentinel."""
    if getattr(arq.connections, "Sentinel", None) is not _AuthenticatedSentinel:
        arq.connections.Sentinel = _AuthenticatedSentinel


def get_redis_settings() -> RedisSettings:
    """
    Get Redis configuration, supporting both direct Redis and Redis Sentinel.

    For Redis Sentinel, set:
    - REDIS=true
    - REDIS_SENTINEL_ENABLED=true
    - REDIS_SENTINEL_HOSTS=host1:port1,host2:port2 (comma-separated)
    - REDIS_SENTINEL_SERVICE_NAME=mymaster (default: mymaster)

    For direct Redis (default):
    - REDIS_HOST=localhost (default: localhost)
    - REDIS_PORT=6379 (default: 6379)
    - REDIS_DB=0 (default: 0)

    Returns:
        RedisSettings: Configured Redis settings for ARQ
    """
    sentinel_enabled = config("REDIS_SENTINEL_ENABLED", cast=bool, default=False)

    ssl_enabled = config("REDIS_SSL", cast=bool, default=False)

    if sentinel_enabled:
        _patch_arq_sentinel()
        sentinel_hosts_str = config("REDIS_SENTINEL_HOSTS", default="localhost:26379")
        sentinel_hosts = []
        for host_port in sentinel_hosts_str.split(","):
            host_port = host_port.strip()
            if ":" in host_port:
                host, port = host_port.split(":", 1)
                sentinel_hosts.append((host.strip(), int(port.strip())))
            else:
                sentinel_hosts.append((host_port, 26379))

        service_name = config("REDIS_SENTINEL_SERVICE_NAME", default="mymaster")

        return RedisSettings(
            host=sentinel_hosts,
            sentinel=True,
            sentinel_master=service_name,
            username=config("REDIS_USERNAME", default=None),
            password=config("REDIS_PASSWORD", default=None),
            database=config("REDIS_DB", cast=int, default=0),
            ssl=ssl_enabled,
            conn_timeout=60,
            conn_retries=10,
            conn_retry_delay=10,
        )
    else:
        return RedisSettings(
            host=config("REDIS_HOST", default="localhost"),
            port=config("REDIS_PORT", cast=int, default=6379),
            username=config("REDIS_USERNAME", default=None),
            password=config("REDIS_PASSWORD", default=None),
            database=config("REDIS_DB", cast=int, default=0),
            ssl=ssl_enabled,
            conn_timeout=60,
            conn_retries=10,
            conn_retry_delay=10,
        )
