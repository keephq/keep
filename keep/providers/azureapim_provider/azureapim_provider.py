"""Azure API Management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AzureAPIMProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Azure Access Token", "sensitive": True},
        default=""
    )
    resource_group: str = dataclasses.field(
        metadata={"required": True, "description": "Azure Resource Group"},
        default=""
    )
    service_name: str = dataclasses.field(
        metadata={"required": True, "description": "Azure API Management Service Name"},
        default=""
    )
    subscription_id: str = dataclasses.field(
        metadata={"required": True, "description": "Azure Subscription ID"},
        default=""
    )

class AzureAPIMProvider(BaseProvider):
    """Azure API Management provider."""
    
    PROVIDER_DISPLAY_NAME = "Azure API Management"
    PROVIDER_CATEGORY = ["API Gateway"]
    AZURE_API = "https://management.azure.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AzureAPIMProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, api_id: str = "", **kwargs: Dict[str, Any]):
        if not api_id:
            raise ProviderException("API ID is required")

        try:
            response = requests.put(
                f"{self.AZURE_API}/subscriptions/{self.authentication_config.subscription_id}/resourceGroups/{self.authentication_config.resource_group}/providers/Microsoft.ApiManagement/service/{self.authentication_config.service_name}/apis/{api_id}",
                params={"api-version": "2021-08-01"},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                json={"properties": kwargs.get("properties", {})},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Azure API Management error: {e}")

        self.logger.info(f"Azure API Management API created: {api_id}")
        return {"status": "success", "api_id": api_id}
