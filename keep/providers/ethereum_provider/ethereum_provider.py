"""Ethereum blockchain provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class EthereumProviderAuthConfig:
    infura_key: str = dataclasses.field(
        metadata={"required": True, "description": "Infura Project ID", "sensitive": True},
        default=""
    )
    private_key: str = dataclasses.field(
        metadata={"required": True, "description": "Ethereum Private Key", "sensitive": True},
        default=""
    )

class EthereumProvider(BaseProvider):
    """Ethereum blockchain provider."""
    
    PROVIDER_DISPLAY_NAME = "Ethereum"
    PROVIDER_CATEGORY = ["Blockchain & Crypto"]
    INFURA_API = "https://mainnet.infura.io/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.INFURA_API}/{self.authentication_config.infura_key}"

    def validate_config(self):
        self.authentication_config = EthereumProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, address: str = "", tx_hash: str = "", **kwargs: Dict[str, Any]):
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
            raise ProviderException(f"Ethereum API error: {e}")

        self.logger.info(f"Ethereum balance checked: {address}")
        return {"status": "success", "address": address}
