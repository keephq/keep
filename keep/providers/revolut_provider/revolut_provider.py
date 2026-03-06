"""Revolut banking provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RevolutProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Revolut API Key", "sensitive": True},
        default=""
    )

class RevolutProvider(BaseProvider):
    """Revolut banking provider."""
    
    PROVIDER_DISPLAY_NAME = "Revolut"
    PROVIDER_CATEGORY = ["Finance & Banking"]
    REVOLUT_API = "https://api.revolut.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RevolutProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, account_id: str = "", amount: float = 0.0, currency: str = "EUR", **kwargs: Dict[str, Any]):
        if not account_id:
            raise ProviderException("Account ID is required")

        self.logger.info(f"Revolut transaction for {amount} {currency}")
        return {"status": "success", "account_id": account_id}
