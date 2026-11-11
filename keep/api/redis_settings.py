"""
Shared Redis configuration module for ARQ pool and worker.

This module provides a centralized way to configure Redis connections,
supporting both direct Redis and Redis Sentinel configurations.

For password-protected Sentinel nodes, set REDIS_SENTINEL_PASSWORD (or fall
back to REDIS_PASSWORD). The Sentinel nodes receive these credentials via
``sentinel_kwargs``, while the data-node master pool uses the regular
``username``/``password`` fields. This works around the fact that arq
0.26.x ``RedisSettings`` has no native ``sentinel_kwargs`` field.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, cast

import arq
import arq.connections as arq_connections
import arq.worker as arq_worker
from arq.connections import ArqRedis, RedisSettings
from arq.constants import default_queue_name, expires_extra_ms
from arq.jobs import Deserializer, Serializer
from redis.exceptions import RedisError

from keep.api.core.config import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentinel-kwargs helper
# ---------------------------------------------------------------------------


def _build_sentinel_kwargs() -> Optional[Dict[str, Any]]:
    """Return kwargs for ``redis.asyncio.sentinel.Sentinel`` to authenticate
    against Sentinel nodes (port 26379), or ``None`` when no Sentinel
    credentials are configured (unauthenticated setups).

    Precedence:
    - ``REDIS_SENTINEL_PASSWORD`` overrides ``REDIS_PASSWORD`` for sentinel auth.
    - ``REDIS_SENTINEL_USERNAME`` overrides ``REDIS_USERNAME`` for sentinel auth.
    - ``REDIS_SENTINEL_SSL`` enables TLS for sentinel connections (default: false).

    Credentials are never logged.
    """
    kwargs: Dict[str, Any] = {}

    sentinel_password: Optional[str] = config(
        "REDIS_SENTINEL_PASSWORD",
        default=config("REDIS_PASSWORD", default=None),
    )
    if sentinel_password:
        kwargs["password"] = sentinel_password

    sentinel_username: Optional[str] = config(
        "REDIS_SENTINEL_USERNAME",
        default=config("REDIS_USERNAME", default=None),
    )
    if sentinel_username:
        kwargs["username"] = sentinel_username

    sentinel_ssl: bool = config(
        "REDIS_SENTINEL_SSL",
        default=False,
        cast=bool,
    )
    if sentinel_ssl:
        kwargs["ssl"] = True

    return kwargs if kwargs else None


# ---------------------------------------------------------------------------
# Custom RedisSettings subclass that carries sentinel_kwargs
# ---------------------------------------------------------------------------


class _SentinelAwareRedisSettings(RedisSettings):
    """``RedisSettings`` subclass that stores ``sentinel_kwargs`` as a plain
    instance attribute (not a dataclass field, so arq's ``create_pool`` won't
    fail with ``TypeError`` for an unexpected keyword argument).

    The patched ``create_pool`` installed by ``_apply_sentinel_patch()``
    inspects this attribute and injects ``sentinel_kwargs`` into the
    ``Sentinel(...)`` constructor when present.
    """

    # Class-level default so the attribute always exists
    _sentinel_kwargs: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        *args: Any,
        sentinel_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._sentinel_kwargs = sentinel_kwargs

    def set_sentinel_kwargs(self, sentinel_kwargs: Optional[Dict[str, Any]]) -> None:
        """Store the sentinel authentication kwargs (never logged)."""
        self._sentinel_kwargs = sentinel_kwargs

    def __repr__(self) -> str:
        d = {
            k: ("***" if "password" in k.lower() else v)
            for k, v in self.__dict__.items()
            if k != "_sentinel_kwargs"
        }
        if self._sentinel_kwargs:
            d["_sentinel_kwargs"] = {
                k: ("***" if "password" in k.lower() else v)
                for k, v in self._sentinel_kwargs.items()
            }
        return f"RedisSettings({', '.join(f'{k}={v!r}' for k, v in d.items())})"


# ---------------------------------------------------------------------------
# Patch arq's create_pool so it honours _sentinel_kwargs
# ---------------------------------------------------------------------------


def _apply_sentinel_patch() -> None:
    """Monkey-patch ``arq.create_pool``, ``arq.connections.create_pool``,
    and ``arq.worker.create_pool`` once at import time so that any
    ``_SentinelAwareRedisSettings`` object with ``_sentinel_kwargs``
    causes the ``Sentinel(...)`` client to receive those credentials.

    This is deliberately narrow: it only affects the Sentinel code-path when
    ``_sentinel_kwargs`` is present and non-empty. All other behaviour
    (direct Redis, no-auth Sentinel) delegates to the original create_pool.
    """
    # Capture the original create_pool exactly once on arq_connections
    if not hasattr(arq_connections, "_keep_orig_create_pool"):
        arq_connections._keep_orig_create_pool = arq_connections.create_pool

    _orig_cp = arq_connections._keep_orig_create_pool

    async def _patched_create_pool(
        settings_: Optional[RedisSettings] = None,
        *,
        retry: int = 0,
        job_serializer: Optional[Serializer] = None,
        job_deserializer: Optional[Deserializer] = None,
        default_queue_name: str = default_queue_name,
        expires_extra_ms: int = expires_extra_ms,
    ) -> ArqRedis:
        settings: RedisSettings = RedisSettings() if settings_ is None else settings_

        sentinel_kwargs: Optional[Dict[str, Any]] = getattr(
            settings, "_sentinel_kwargs", None
        )

        # Only intercept sentinel with non-empty sentinel_kwargs
        if settings.sentinel and sentinel_kwargs:
            if isinstance(settings.host, str) and settings.sentinel:
                raise RuntimeError(
                    "str provided for 'host' but 'sentinel' is true; "
                    "list of sentinels expected"
                )

            def pool_factory(*args: Any, **kwargs: Any) -> ArqRedis:
                import redis.asyncio.sentinel as _sentinel_mod

                client = _sentinel_mod.Sentinel(
                    *args,
                    sentinels=settings.host,
                    sentinel_kwargs=sentinel_kwargs,
                    ssl=settings.ssl,
                    **kwargs,
                )
                redis = client.master_for(
                    settings.sentinel_master, redis_class=ArqRedis
                )
                return cast(ArqRedis, redis)

            while True:
                try:
                    pool = pool_factory(
                        db=settings.database,
                        username=settings.username,
                        password=settings.password,
                        encoding="utf8",
                    )
                    pool.job_serializer = job_serializer
                    pool.job_deserializer = job_deserializer
                    pool.default_queue_name = default_queue_name
                    pool.expires_extra_ms = expires_extra_ms
                    await pool.ping()
                except (
                    ConnectionError,
                    OSError,
                    RedisError,
                    asyncio.TimeoutError,
                ) as e:
                    if retry < settings.conn_retries:
                        logger.warning(
                            "redis connection error %s:%s %s %s, %s retries remaining...",
                            settings.host,
                            settings.port,
                            e.__class__.__name__,
                            e,
                            settings.conn_retries - retry,
                        )
                        await asyncio.sleep(settings.conn_retry_delay)
                        retry = retry + 1
                    else:
                        raise
                else:
                    if retry > 0:
                        logger.info("redis connection successful")
                    return pool

        # All other cases (direct Redis, or Sentinel without sentinel credentials)
        # delegate to the ORIGINAL create_pool
        return await arq_connections._keep_orig_create_pool(
            settings_,
            retry=retry,
            job_serializer=job_serializer,
            job_deserializer=job_deserializer,
            default_queue_name=default_queue_name,
            expires_extra_ms=expires_extra_ms,
        )

    # Patch top-level arq, connections, and worker
    arq.create_pool = _patched_create_pool
    arq_connections.create_pool = _patched_create_pool
    arq_worker.create_pool = _patched_create_pool


# Apply the patch immediately on module import
_apply_sentinel_patch()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_redis_settings() -> RedisSettings:
    """
    Get Redis configuration, supporting both direct Redis and Redis Sentinel.

    For Redis Sentinel, set:
    - REDIS=true
    - REDIS_SENTINEL_ENABLED=true
    - REDIS_SENTINEL_HOSTS=host1:port1,host2:port2 (comma-separated)
    - REDIS_SENTINEL_SERVICE_NAME=mymaster (default: mymaster)

    For password-protected Sentinel nodes (optional):
    - REDIS_SENTINEL_PASSWORD  (falls back to REDIS_PASSWORD when unset)
    - REDIS_SENTINEL_USERNAME  (falls back to REDIS_USERNAME when unset)
    - REDIS_SENTINEL_SSL       (default: false; opt-in TLS for sentinel nodes)

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

        settings = _SentinelAwareRedisSettings(
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
        # Attach sentinel-node credentials (not exposed in logs or repr)
        sentinel_kwargs = _build_sentinel_kwargs()
        settings.set_sentinel_kwargs(sentinel_kwargs)
        return settings
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
