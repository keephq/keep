"""Power BI data visualization provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PowerBIProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Power BI Access Token", "sensitive": True},
        default=""
    )

class PowerBIProvider(BaseProvider):
    """Power BI data visualization provider."""
    
    PROVIDER_DISPLAY_NAME = "Power BI"
    PROVIDER_CATEGORY = ["Data Analytics"]
    POWERBI_API = "https://api.powerbi.com/v1.0/myorg"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PowerBIProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, dataset_id: str = "", group_id: str = "", **kwargs: Dict[str, Any]):
        if not dataset_id:
            raise ProviderException("Dataset ID is required")

        try:
            url = f"{self.POWERBI_API}/groups/{group_id}/datasets/{dataset_id}/refreshes" if group_id else f"{self.POWERBI_API}/datasets/{dataset_id}/refreshes"
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Power BI API error: {e}")

        self.logger.info(f"Power BI dataset refreshed: {dataset_id}")
        return {"status": "success", "dataset_id": dataset_id}
