"""Sisense business intelligence provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SisenseProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Sisense API Token", "sensitive": True},
        default=""
    )
    server_url: str = dataclasses.field(
        metadata={"required": True, "description": "Sisense Server URL"},
        default=""
    )

class SisenseProvider(BaseProvider):
    """Sisense business intelligence provider."""
    
    PROVIDER_DISPLAY_NAME = "Sisense"
    PROVIDER_CATEGORY = ["Data Analytics"]
    SISENSE_API = "api/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.authentication_config.server_url}/{self.SISENSE_API}"

    def validate_config(self):
        self.authentication_config = SisenseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, dashboard_id: str = "", **kwargs: Dict[str, Any]):
        if not dashboard_id:
            raise ProviderException("Dashboard ID is required")

        try:
            response = requests.post(
                f"{self.api_url}/dashboards/{dashboard_id}/refresh",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sisense API error: {e}")

        self.logger.info(f"Sisense dashboard refreshed: {dashboard_id}")
        return {"status": "success", "dashboard_id": dashboard_id}
