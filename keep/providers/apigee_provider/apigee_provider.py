"""Apigee API management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ApigeeProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Apigee Access Token", "sensitive": True},
        default=""
    )
    organization: str = dataclasses.field(
        metadata={"required": True, "description": "Apigee Organization"},
        default=""
    )

class ApigeeProvider(BaseProvider):
    """Apigee API management provider."""
    
    PROVIDER_DISPLAY_NAME = "Apigee"
    PROVIDER_CATEGORY = ["API Gateway"]
    APIGEE_API = "https://apigee.googleapis.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ApigeeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, proxy_name: str = "", revision: str = "", **kwargs: Dict[str, Any]):
        if not proxy_name:
            raise ProviderException("Proxy name is required")

        try:
            response = requests.post(
                f"{self.APIGEE_API}/organizations/{self.authentication_config.organization}/apis/{proxy_name}/revisions/{revision}/deployments",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Apigee API error: {e}")

        self.logger.info(f"Apigee proxy deployed: {proxy_name}")
        return {"status": "success", "proxy_name": proxy_name}
