"""DHL shipping provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DHLProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "DHL API Key", "sensitive": True},
        default=""
    )
    account_number: str = dataclasses.field(
        metadata={"required": True, "description": "DHL Account Number"},
        default=""
    )

class DHLProvider(BaseProvider):
    """DHL shipping provider."""
    
    PROVIDER_DISPLAY_NAME = "DHL"
    PROVIDER_CATEGORY = ["Shipping & Logistics"]
    DHL_API = "https://api-eu.dhl.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DHLProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, tracking_number: str = "", **kwargs: Dict[str, Any]):
        if not tracking_number:
            raise ProviderException("Tracking number is required")

        try:
            response = requests.get(
                f"{self.DHL_API}/track/shipments/{tracking_number}",
                headers={
                    "DHL-API-Key": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"DHL API error: {e}")

        self.logger.info(f"DHL tracking info retrieved: {tracking_number}")
        return {"status": "success", "tracking_number": tracking_number}
