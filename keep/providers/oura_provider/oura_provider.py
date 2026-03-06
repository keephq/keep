"""Oura Ring health tracking provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OuraProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Oura Access Token", "sensitive": True},
        default=""
    )

class OuraProvider(BaseModel):
    """Oura Ring health tracking provider."""
    
    PROVIDER_DISPLAY_NAME = "Oura Ring"
    PROVIDER_CATEGORY = ["Health & Fitness"]
    OURA_API = "https://api.ouraring.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OuraProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, metric: str = "", value: str = "", **kwargs: Dict[str, Any]):
        if not metric or not value:
            raise ProviderException("Metric and value are required")

        self.logger.info(f"Oura Ring data logged: {metric}")
        return {"status": "success", "metric": metric}
