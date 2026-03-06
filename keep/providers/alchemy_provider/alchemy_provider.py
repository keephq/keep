"""Alchemy blockchain infrastructure provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AlchemyProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Alchemy API Key", "sensitive": True},
        default=""
    )

class AlchemyProvider(BaseProvider):
    """Alchemy blockchain infrastructure provider."""
    
    PROVIDER_DISPLAY_NAME = "Alchemy"
    PROVIDER_CATEGORY = ["Blockchain & Crypto"]
    ALCHEMY_API = "https://eth-mainnet.alchemyapi.io/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.ALCHEMY_API}/{self.authentication_config.api_key}"

    def validate_config(self):
        self.authentication_config = AlchemyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, address: str = "", action: str = "", **kwargs: Dict[str, Any]):
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
            raise ProviderException(f"Alchemy API error: {e}")

        self.logger.info(f"Alchemy balance checked: {address}")
        return {"status": "success", "address": address}
