"""Recorded Future threat intelligence provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RecordedFutureProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Recorded Future API Key", "sensitive": True},
        default=""
    )

class RecordedFutureProvider(BaseProvider):
    """Recorded Future threat intelligence provider."""
    
    PROVIDER_DISPLAY_NAME = "Recorded Future"
    PROVIDER_CATEGORY = ["Security"]
    RF_API = "https://api.recordedfuture.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RecordedFutureProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, indicator: str = "", **kwargs: Dict[str, Any]):
        if not indicator:
            raise ProviderException("Indicator is required")

        try:
            response = requests.get(
                f"{self.RF_API}/intelligence",
                params={"entity": indicator},
                headers={"X-RFToken": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Recorded Future API error: {e}")

        self.logger.info(f"Recorded Future intelligence retrieved: {indicator}")
        return {"status": "success", "indicator": indicator}
