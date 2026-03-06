"""PandaDoc document automation provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PandaDocProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "PandaDoc API Key", "sensitive": True},
        default=""
    )

class PandaDocProvider(BaseProvider):
    """PandaDoc document automation provider."""
    
    PROVIDER_DISPLAY_NAME = "PandaDoc"
    PROVIDER_CATEGORY = ["Legal & Compliance"]
    PANDADOC_API = "https://api.pandadoc.com/public/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PandaDocProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, document_id: str = "", **kwargs: Dict[str, Any]):
        if not document_id:
            raise ProviderException("Document ID is required")

        try:
            response = requests.get(
                f"{self.PANDADOC_API}/documents/{document_id}",
                headers={
                    "Authorization": f"API-Key {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"PandaDoc API error: {e}")

        self.logger.info(f"PandaDoc document retrieved: {document_id}")
        return {"status": "success", "document_id": document_id}
