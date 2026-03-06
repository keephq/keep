"""SignNow e-signature provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SignNowProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "SignNow Access Token", "sensitive": True},
        default=""
    )

class SignNowProvider(BaseProvider):
    """SignNow e-signature provider."""
    
    PROVIDER_DISPLAY_NAME = "SignNow"
    PROVIDER_CATEGORY = ["Legal & Compliance"]
    SIGNNOW_API = "https://api.signnow.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SignNowProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, document_id: str = "", **kwargs: Dict[str, Any]):
        if not document_id:
            raise ProviderException("Document ID is required")

        try:
            response = requests.get(
                f"{self.SIGNNOW_API}/document/{document_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"SignNow API error: {e}")

        self.logger.info(f"SignNow document retrieved: {document_id}")
        return {"status": "success", "document_id": document_id}
