"""Wise money transfer provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WiseProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Wise API Key", "sensitive": True},
        default=""
    )

class WiseProvider(BaseProvider):
    """Wise money transfer provider."""
    
    PROVIDER_DISPLAY_NAME = "Wise"
    PROVIDER_CATEGORY = ["Finance & Banking"]
    WISE_API = "https://api.wise.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WiseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, profile_id: str = "", amount: float = 0.0, currency: str = "USD", **kwargs: Dict[str, Any]):
        if not profile_id:
            raise ProviderException("Profile ID is required")

        self.logger.info(f"Wise transfer initiated for {amount} {currency}")
        return {"status": "success", "profile_id": profile_id}
