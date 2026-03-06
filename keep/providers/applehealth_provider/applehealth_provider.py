"""Apple Health fitness tracking provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AppleHealthProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Apple Health API Key", "sensitive": True},
        default=""
    )

class AppleHealthProvider(BaseModel):
    """Apple Health fitness tracking provider."""
    
    PROVIDER_DISPLAY_NAME = "Apple Health"
    PROVIDER_CATEGORY = ["Health & Fitness"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AppleHealthProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, health_metric: str = "", value: str = "", **kwargs: Dict[str, Any]):
        if not health_metric or not value:
            raise ProviderException("Health metric and value are required")

        self.logger.info(f"Apple Health data logged: {health_metric}")
        return {"status": "success", "metric": health_metric}
