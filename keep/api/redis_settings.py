"""
Shared Redis configuration module for ARQ pool and worker.

This module provides a centralized way to configure Redis connections,
supporting both direct Redis and Redis Sentinel configurations.
"""

from arq.connections import RedisSettings
from keep.api.core.config import config


def get_redis_settings() -> RedisSettings:
    """
    Get Redis configuration, supporting both direct Redis and Redis Sentinel.
    
    For Redis Sentinel, set:
    - REDIS_SENTINEL_ENABLED=true
    - REDIS_SENTINEL_HOSTS=host1:port1,host2:port2 (comma-separated)
    - REDIS_SENTINEL_SERVICE_NAME=mymaster (default: mymaster)
    
    For direct Redis (default):
    - REDIS_HOST=localhost (default: localhost)
    - REDIS_PORT=6379 (default: 6379)
    
    Returns:
        RedisSettings: Configured Redis settings for ARQ
    """
    sentinel_enabled = config("REDIS_SENTINEL_ENABLED", cast=bool, default=False)
    
    if sentinel_enabled:
        # Parse sentinel hosts from comma-separated string
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
            conn_timeout=60,
            conn_retries=10,
            conn_retry_delay=10,
        )