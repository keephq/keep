"""Polygon blockchain provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PolygonProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Polygon API Key", "sensitive": True},
        default=""
    )

class PolygonProvider(BaseProvider):
    """Polygon blockchain provider."""
    
    PROVIDER_DISPLAY_NAME = "Polygon"
    PROVIDER_CATEGORY = ["Blockchain & Crypto"]
    POLYGON_API = "https://polygon-mainnet.g.alchemy.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.POLYGON_API}/{self.authentication_config.api_key}"

    def validate_config(self):
        self.authentication_config = PolygonProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, address: str = "", **kwargs: Dict[str, Any]):
        if not address:
            raise ProviderException("Address is required")

        try:
            response = requests.post(
                self.api_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [address, "latest"],
                    "id": 1
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Polygon API error: {e}")

        self.logger.info(f"Polygon balance checked: {address}")
        return {"status": "success", "address": address}
