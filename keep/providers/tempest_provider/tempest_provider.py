"""Tempest security monitoring provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TempestProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Tempest API Key", "sensitive": True},
        default=""
    )

class TempestProvider(BaseModel):
    """Tempest security monitoring provider."""
    
    PROVIDER_DISPLAY_NAME = "Tempest Security"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TempestProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, alert_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not alert_id:
            raise ProviderException("Alert ID is required")

        self.logger.info(f"Tempest security alert {alert_id}: {action}")
        return {"status": "success", "alert_id": alert_id}
