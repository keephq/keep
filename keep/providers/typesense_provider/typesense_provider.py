"""Typesense search provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class TypesenseProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Typesense API Key", "sensitive": True}, default="")
    host_url: str = dataclasses.field(metadata={"required": True, "description": "Typesense Host URL"}, default="")

class TypesenseProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Typesense"
    PROVIDER_CATEGORY = ["Search"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TypesenseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, collection_name: str = "", query: dict = None, **kwargs: Dict[str, Any]):
        if not collection_name or not query:
            raise ProviderException("Collection name and query are required")
        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/collections/{collection_name}/documents/search",
                params=query,
                headers={"X-TYPESENSE-API-KEY": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Typesense API error: {e}")
        self.logger.info(f"Typesense search executed on {collection_name}")
        return {"status": "success", "collection_name": collection_name}
