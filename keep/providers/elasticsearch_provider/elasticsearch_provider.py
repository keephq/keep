"""ElasticSearch search provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class ElasticSearchProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "ElasticSearch API Key", "sensitive": True}, default="")
    endpoint_url: str = dataclasses.field(metadata={"required": True, "description": "ElasticSearch Endpoint URL"}, default="")

class ElasticSearchProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "ElasticSearch"
    PROVIDER_CATEGORY = ["Search"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ElasticSearchProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, index: str = "", query: dict = None, **kwargs: Dict[str, Any]):
        if not index or not query:
            raise ProviderException("Index and query are required")
        try:
            response = requests.post(
                f"{self.authentication_config.endpoint_url}/{index}/_search",
                json=query,
                headers={
                    "Authorization": f"ApiKey {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"ElasticSearch API error: {e}")
        self.logger.info(f"ElasticSearch query executed on {index}")
        return {"status": "success", "index": index}
