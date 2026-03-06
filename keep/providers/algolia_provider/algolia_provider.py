"""Algolia search provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class AlgoliaProviderAuthConfig:
    application_id: str = dataclasses.field(metadata={"required": True, "description": "Algolia Application ID"}, default="")
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Algolia API Key", "sensitive": True}, default="")

class AlgoliaProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Algolia"
    PROVIDER_CATEGORY = ["Search"]
    ALGOLIA_API = "https://{app_id}.algolia.net/1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = self.ALGOLIA_API.format(app_id=self.authentication_config.application_id)

    def validate_config(self):
        self.authentication_config = AlgoliaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, index_name: str = "", object_id: str = "", **kwargs: Dict[str, Any]):
        if not index_name or not object_id:
            raise ProviderException("Index name and object ID are required")
        try:
            response = requests.get(
                f"{self.api_url}/indexes/{index_name}/{object_id}",
                headers={
                    "X-Algolia-Application-Id": self.authentication_config.application_id,
                    "X-Algolia-API-Key": self.authentication_config.api_key
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Algolia API error: {e}")
        self.logger.info(f"Algolia object retrieved: {object_id}")
        return {"status": "success", "object_id": object_id}
