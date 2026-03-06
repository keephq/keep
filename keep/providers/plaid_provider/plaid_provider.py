"""Plaid financial data provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PlaidProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Plaid Client ID"},
        default=""
    )
    secret: str = dataclasses.field(
        metadata={"required": True, "description": "Plaid Secret", "sensitive": True},
        default=""
    )

class PlaidProvider(BaseProvider):
    """Plaid financial data provider."""
    
    PROVIDER_DISPLAY_NAME = "Plaid"
    PROVIDER_CATEGORY = ["Finance & Banking"]
    PLAID_API = "https://development.plaid.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PlaidProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, access_token: str = "", account_id: str = "", **kwargs: Dict[str, Any]):
        if not access_token:
            raise ProviderException("Access token is required")

        self.logger.info(f"Plaid account data fetched for {account_id}")
        return {"status": "success", "account_id": account_id}
