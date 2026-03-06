"""Apache Solr search provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class SolrProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Solr API Key", "sensitive": True}, default="")
    solr_url: str = dataclasses.field(metadata={"required": True, "description": "Solr URL"}, default="")

class SolrProvider(BaseModel):
    PROVIDER_DISPLAY_NAME = "Apache Solr"
    PROVIDER_CATEGORY = ["Search"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolrProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, core: str = "", query: str = "", **kwargs: Dict[str, Any]):
        if not core or not query:
            raise ProviderException("Core and query are required")
        try:
            response = requests.get(
                f"{self.authentication_config.solr_url}/{core}/select",
                params={"q": query, "wt": "json"},
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Solr API error: {e}")
        self.logger.info(f"Solr query executed on {core}")
        return {"status": "success", "core": core}
