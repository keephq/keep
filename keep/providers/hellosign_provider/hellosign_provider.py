"""HelloSign e-signature provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HelloSignProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "HelloSign API Key", "sensitive": True},
        default=""
    )

class HelloSignProvider(BaseProvider):
    """HelloSign e-signature provider."""
    
    PROVIDER_DISPLAY_NAME = "HelloSign"
    PROVIDER_CATEGORY = ["Legal & Compliance"]
    HELLOSIGN_API = "https://api.hellosign.com/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HelloSignProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, signature_request_id: str = "", **kwargs: Dict[str, Any]):
        if not signature_request_id:
            raise ProviderException("Signature request ID is required")

        try:
            response = requests.get(
                f"{self.HELLOSIGN_API}/signature_request/{signature_request_id}",
                auth=(self.authentication_config.api_key, ""),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"HelloSign API error: {e}")

        self.logger.info(f"HelloSign signature request retrieved: {signature_request_id}")
        return {"status": "success", "signature_request_id": signature_request_id}
