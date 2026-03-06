"""Tableau data visualization provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TableauProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Tableau API Key", "sensitive": True},
        default=""
    )
    server_url: str = dataclasses.field(
        metadata={"required": True, "description": "Tableau Server URL"},
        default=""
    )

class TableauProvider(BaseProvider):
    """Tableau data visualization provider."""
    
    PROVIDER_DISPLAY_NAME = "Tableau"
    PROVIDER_CATEGORY = ["Data Analytics"]
    TABLEAU_API = "api/3.4"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"{self.authentication_config.server_url}/{self.TABLEAU_API}"

    def validate_config(self):
        self.authentication_config = TableauProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, workbook_id: str = "", view_id: str = "", **kwargs: Dict[str, Any]):
        if not workbook_id:
            raise ProviderException("Workbook ID is required")

        try:
            response = requests.post(
                f"{self.api_url}/sites/default/workbooks/{workbook_id}/views/{view_id}/refresh",
                headers={
                    "X-Tableau-Auth": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Tableau API error: {e}")

        self.logger.info(f"Tableau view refreshed: {view_id}")
        return {"status": "success", "view_id": view_id}
