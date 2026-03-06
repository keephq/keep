"""Meilisearch search provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class MeilisearchProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Meilisearch API Key", "sensitive": True}, default="")
    host_url: str = dataclasses.field(metadata={"required": True, "description": "Meilisearch Host URL"}, default="")

class MeilisearchProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Meilisearch"
    PROVIDER_CATEGORY = ["Search"]
    MEILISEARCH_API = "indexes"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.authentication_config.host_url}/{self.MEILISEARCH_API}"

    def validate_config(self):
        self.authentication_config = MeilisearchProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, index_uid: str = "", query: str = "", **kwargs: Dict[str, Any]):
        if not index_uid or not query:
            raise ProviderException("Index UID and query are required")
        try:
            response = requests.post(
                f"{self.api_url}/{index_uid}/search",
                json={"q": query},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Meilisearch API error: {e}")
        self.logger.info(f"Meilisearch query executed on {index_uid}")
        return {"status": "success", "index_uid": index_uid}
