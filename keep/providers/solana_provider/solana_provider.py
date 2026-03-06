"""Solana blockchain provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SolanaProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Solana API Key", "sensitive": True},
        default=""
    )

class SolanaProvider(BaseProvider):
    """Solana blockchain provider."""
    
    PROVIDER_DISPLAY_NAME = "Solana"
    PROVIDER_CATEGORY = ["Blockchain & Crypto"]
    SOLANA_API = "https://api.mainnet-beta.solana.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolanaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, address: str = "", **kwargs: Dict[str, Any]):
        if not address:
            raise ProviderException("Address is required")

        try:
            response = requests.post(
                self.SOLANA_API,
                json={
                    "jsonrpc": "2.0",
                    "method": "getBalance",
                    "params": [address],
                    "id": 1
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Solana API error: {e}")

        self.logger.info(f"Solana balance checked: {address}")
        return {"status": "success", "address": address}
