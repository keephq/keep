"""Metabase business intelligence provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MetabaseProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Metabase API Key", "sensitive": True},
        default=""
    )
    server_url: str = dataclasses.field(
        metadata={"required": True, "description": "Metabase Server URL"},
        default=""
    )

class MetabaseProvider(BaseModel):
    """Metabase business intelligence provider."""
    
    PROVIDER_DISPLAY_NAME = "Metabase"
    PROVIDER_CATEGORY = ["Data Analytics"]
    METABASE_API = "api"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.authentication_config.server_url}/{self.METABASE_API}"

    def validate_config(self):
        self.authentication_config = MetabaseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, dashboard_id: str = "", **kwargs: Dict[str, Any]):
        if not dashboard_id:
            raise ProviderException("Dashboard ID is required")

        try:
            response = requests.post(
                f"{self.api_url}/dashboard/{dashboard_id}/refresh",
                headers={
                    "X-API-Key": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Metabase API error: {e}")

        self.logger.info(f"Metabase dashboard refreshed: {dashboard_id}")
        return {"status": "success", "dashboard_id": dashboard_id}
