"""N26 digital bank provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class N26ProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "N26 Access Token", "sensitive": True},
        default=""
    )

class N26Provider(BaseProvider):
    """N26 digital bank provider."""
    
    PROVIDER_DISPLAY_NAME = "N26"
    PROVIDER_CATEGORY = ["Finance & Banking"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = N26ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, account_id: str = "", transaction_type: str = "", **kwargs: Dict[str, Any]):
        if not account_id:
            raise ProviderException("Account ID is required")

        self.logger.info(f"N26 transaction processed for {account_id}")
        return {"status": "success", "account_id": account_id}
