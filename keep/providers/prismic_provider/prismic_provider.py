"""Prismic headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PrismicProviderAuthConfig:
    api_endpoint: str = dataclasses.field(
        metadata={"required": True, "description": "Prismic API Endpoint"},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Prismic Access Token", "sensitive": True},
        default=""
    )

class PrismicProvider(BaseProvider):
    """Prismic headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Prismic"
    PROVIDER_CATEGORY = ["Content Management"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PrismicProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, document_id: str = "", **kwargs: Dict[str, Any]):
        if not document_id:
            raise ProviderException("Document ID is required")

        try:
            response = requests.get(
                f"{self.authentication_config.api_endpoint}/api/v2/documents/{document_id}",
                params={"access_token": self.authentication_config.access_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Prismic API error: {e}")

        self.logger.info(f"Prismic document retrieved: {document_id}")
        return {"status": "success", "document_id": document_id}
