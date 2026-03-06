"""Lyft ridesharing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LyftProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Lyft Access Token", "sensitive": True},
        default=""
    )

class LyftProvider(BaseModel):
    """Lyft ridesharing provider."""
    
    PROVIDER_DISPLAY_NAME = "Lyft"
    PROVIDER_CATEGORY = ["Travel & Transportation"]
    LYFT_API = "https://api.lyft.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LyftProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, ride_type: str = "", origin: str = "", **kwargs: Dict[str, Any]):
        if not ride_type or not origin:
            raise ProviderException("Ride type and origin are required")

        self.logger.info(f"Lyft ride requested: {ride_type}")
        return {"status": "success", "ride_type": ride_type}
