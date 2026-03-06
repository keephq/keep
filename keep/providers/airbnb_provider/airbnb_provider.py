"""Airbnb accommodation provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AirbnbProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Airbnb API Key", "sensitive": True},
        default=""
    )

class AirbnbProvider(BaseModel):
    """Airbnb accommodation provider."""
    
    PROVIDER_DISPLAY_NAME = "Airbnb"
    PROVIDER_CATEGORY = ["Travel & Transportation"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AirbnbProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, listing_id: str = "", check_in: str = "", check_out: str = "", **kwargs: Dict[str, Any]):
        if not listing_id:
            raise ProviderException("Listing ID is required")

        self.logger.info(f"Airbnb booking for listing {listing_id}")
        return {"status": "success", "listing_id": listing_id}
