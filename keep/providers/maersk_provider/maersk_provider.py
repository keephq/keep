"""Maersk shipping provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MaerskProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Maersk API Key", "sensitive": True},
        default=""
    )
    customer_number: str = dataclasses.field(
        metadata={"required": True, "description": "Maersk Customer Number"},
        default=""
    )

class MaerskProvider(BaseProvider):
    """Maersk shipping provider."""
    
    PROVIDER_DISPLAY_NAME = "Maersk"
    PROVIDER_CATEGORY = ["Shipping & Logistics"]
    MAERSK_API = "https://api.maersk.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MaerskProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, tracking_number: str = "", **kwargs: Dict[str, Any]):
        if not tracking_number:
            raise ProviderException("Tracking number is required")

        try:
            response = requests.get(
                f"{self.MAERSK_API}/tracking/{tracking_number}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Maersk API error: {e}")
        self.logger.info(f"Maersk tracking info retrieved: {tracking_number}")
        return {"status": "success", "tracking_number": tracking_number}
