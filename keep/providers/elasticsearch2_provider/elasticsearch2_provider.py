"""Elasticsearch provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class Elasticsearch2ProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Elasticsearch Host URL"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"description": "API Key", "sensitive": True},
        default=""
    )

class Elasticsearch2Provider(BaseProvider):
    """Elasticsearch provider."""
    
    PROVIDER_DISPLAY_NAME = "Elasticsearch"
    PROVIDER_CATEGORY = ["Database"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Elasticsearch2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, index: str = "", document: Dict = None, **kwargs: Dict[str, Any]):
        if not index or not document:
            raise ProviderException("Index and document are required")

        headers = {"Content-Type": "application/json"}
        if self.authentication_config.api_key:
            headers["Authorization"] = f"ApiKey {self.authentication_config.api_key}"

        try:
            response = requests.post(
                f"{self.authentication_config.host}/{index}/_doc",
                json=document,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Elasticsearch API error: {e}")

        self.logger.info("Elasticsearch document indexed")
        return {"status": "success"}
