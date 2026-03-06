"""Apartments.com rental provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ApartmentsProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Apartments.com API Key", "sensitive": True},
        default=""
    )

class ApartmentsProvider(BaseProvider):
    """Apartments.com rental provider."""
    
    PROVIDER_DISPLAY_NAME = "Apartments.com"
    PROVIDER_CATEGORY = ["Real Estate"]
    APARTMENTS_API = "https://api.apartments.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ApartmentsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, listing_id: str = "", **kwargs: Dict[str, Any]):
        if not listing_id:
            raise ProviderException("Listing ID is required")

        try:
            response = requests.get(
                f"{self.APARTMENTS_API}/listings/{listing_id}",
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Apartments.com API error: {e}")

        self.logger.info(f"Apartments.com listing data retrieved: {listing_id}")
        return {"status": "success", "listing_id": listing_id}
