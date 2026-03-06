"""Garmin fitness tracking provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GarminProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Garmin API Key", "sensitive": True},
        default=""
    )

class GarminProvider(BaseModel):
    """Garmin fitness tracking provider."""
    
    PROVIDER_DISPLAY_NAME = "Garmin"
    PROVIDER_CATEGORY = ["Health & Fitness"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GarminProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, device_id: str = "", activity: str = "", **kwargs: Dict[str, Any]):
        if not device_id or not activity:
            raise ProviderException("Device ID and activity are required")

        self.logger.info(f"Garmin activity logged for {device_id}")
        return {"status": "success", "device_id": device_id}
