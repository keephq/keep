"""Redis database provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


@pydantic.dataclasses.dataclass
class RedisProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Redis Host"},
        default=""
    )
    port: int = dataclasses.field(
        metadata={"description": "Redis Port"},
        default=6379
    )
    password: str = dataclasses.field(
        metadata={"description": "Password", "sensitive": True},
        default=""
    )
    db: int = dataclasses.field(
        metadata={"description": "Database Number"},
        default=0
    )

class RedisProvider(BaseProvider):
    """Redis database provider."""
    
    PROVIDER_DISPLAY_NAME = "Redis"
    PROVIDER_CATEGORY = ["Database"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RedisProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, key: str = "", value: str = "", ttl: int = None, **kwargs: Dict[str, Any]):
        if not key or not value:
            raise ProviderException("Key and value are required")

        if not HAS_REDIS:
            raise ProviderException("redis is not installed")

        try:
            r = redis.Redis(
                host=self.authentication_config.host,
                port=self.authentication_config.port,
                password=self.authentication_config.password or None,
                db=self.authentication_config.db
            )
            r.set(key, value, ex=ttl)
        except Exception as e:
            raise ProviderException(f"Redis error: {e}")

        self.logger.info("Redis key set")
        return {"status": "success"}
