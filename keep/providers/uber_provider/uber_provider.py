"""Uber ridesharing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class UberProviderAuthConfig:
    server_token: str = dataclasses.field(
        metadata={"required": True, "description": "Uber Server Token", "sensitive": True},
        default=""
    )

class UberProvider(BaseModel):
    """Uber ridesharing provider."""
    
    PROVIDER_DISPLAY_NAME = "Uber"
    PROVIDER_CATEGORY = ["Travel & Transportation"]
    UBER_API = "https://api.uber.com/v1.2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = UberProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, product_id: str = "", start_lat: float = 0.0, start_lng: float = 0.0, **kwargs: Dict[str, Any]):
        if not product_id:
            raise ProviderException("Product ID is required")

        self.logger.info(f"Uber ride requested: {product_id}")
        return {"status": "success", "product_id": product_id}
