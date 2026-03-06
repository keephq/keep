"""Trulia real estate provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TruliaProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Trulia API Key", "sensitive": True},
        default=""
    )

class TruliaProvider(BaseProvider):
    """Trulia real estate provider."""
    
    PROVIDER_DISPLAY_NAME = "Trulia"
    PROVIDER_CATEGORY = ["Real Estate"]
    TRULIA_API = "https://api.trulia.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TruliaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, property_id: str = "", **kwargs: Dict[str, Any]):
        if not property_id:
            raise ProviderException("Property ID is required")

        try:
            response = requests.get(
                f"{self.TRULIA_API}/properties/{property_id}",
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Trulia API error: {e}")

        self.logger.info(f"Trulia property data retrieved: {property_id}")
        return {"status": "success", "property_id": property_id}
