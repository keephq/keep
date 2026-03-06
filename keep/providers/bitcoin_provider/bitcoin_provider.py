"""Bitcoin blockchain provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BitcoinProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Blockchain.com API Key", "sensitive": True},
        default=""
    )

class BitcoinProvider(BaseProvider):
    """Bitcoin blockchain provider."""
    
    PROVIDER_DISPLAY_NAME = "Bitcoin"
    PROVIDER_CATEGORY = ["Blockchain & Crypto"]
    BLOCKCHAIN_API = "https://api.blockchain.com/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BitcoinProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, address: str = "", tx_hash: str = "", **kwargs: Dict[str, Any]):
        if not address:
            raise ProviderException("Address is required")

        try:
            response = requests.get(
                f"{self.BLOCKCHAIN_API}/btc/main/addresses/{address}",
                headers={
                    "X-API-Key": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Bitcoin API error: {e}")

        self.logger.info(f"Bitcoin address checked: {address}")
        return {"status": "success", "address": address}
