"""Monzo digital bank provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MonzoProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Monzo Access Token", "sensitive": True},
        default=""
    )

class MonzoProvider(BaseProvider):
    """Monzo digital bank provider."""
    
    PROVIDER_DISPLAY_NAME = "Monzo"
    PROVIDER_CATEGORY = ["Finance & Banking"]
    MONZO_API = "https://api.monzo.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MonzoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, account_id: str = "", amount: int = 0, currency: str = "GBP", **kwargs: Dict[str, Any]):
        if not account_id:
            raise ProviderException("Account ID is required")

        self.logger.info(f"Monzo transaction for {amount/100} {currency}")
        return {"status": "success", "account_id": account_id}
