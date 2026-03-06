"""Render cloud platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RenderProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Render API Key", "sensitive": True},
        default=""
    )

class RenderProvider(BaseProvider):
    """Render cloud platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Render"
    PROVIDER_CATEGORY = ["Web Hosting"]
    RENDER_API = "https://api.render.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RenderProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, service_id: str = "", **kwargs: Dict[str, Any]):
        if not service_id:
            raise ProviderException("Service ID is required")

        try:
            response = requests.post(
                f"{self.RENDER_API}/services/{service_id}/deploys",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Accept": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Render API error: {e}")

        self.logger.info(f"Render deployment triggered: {service_id}")
        return {"status": "success", "service_id": service_id}
