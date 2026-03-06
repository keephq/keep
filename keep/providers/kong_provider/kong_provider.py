"""Kong API gateway provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class KongProviderAuthConfig:
    admin_api_url: str = dataclasses.field(
        metadata={"required": True, "description": "Kong Admin API URL"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Kong API Key", "sensitive": True},
        default=""
    )

class KongProvider(BaseModel):
    """Kong API gateway provider."""
    
    PROVIDER_DISPLAY_NAME = "Kong"
    PROVIDER_CATEGORY = ["API Gateway"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = KongProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, service_name: str = "", upstream_url: str = "", **kwargs: Dict[str, Any]):
        if not service_name or not upstream_url:
            raise ProviderException("Service name and upstream URL are required")

        payload = {
            "name": service_name,
            "url": upstream_url
        }

        try:
            response = requests.post(
                f"{self.authentication_config.admin_api_url}/services",
                json=payload,
                headers={
                    "Kong-Admin-Token": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Kong API error: {e}")

        self.logger.info(f"Kong service created: {service_name}")
        return {"status": "success", "service_name": service_name}
