"""Tyk API gateway provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TykProviderAuthConfig:
    api_url: str = dataclasses.field(
        metadata={"required": True, "description": "Tyk API URL"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Tyk API Key", "sensitive": True},
        default=""
    )

class TykProvider(BaseProvider):
    """Tyk API gateway provider."""
    
    PROVIDER_DISPLAY_NAME = "Tyk"
    PROVIDER_CATEGORY = ["API Gateway"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TykProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, api_name: str = "", target_url: str = "", **kwargs: Dict[str, Any]):
        if not api_name or not target_url:
            raise ProviderException("API name and target URL are required")

        payload = {
            "api_definition": {
                "name": api_name,
                "proxy": {
                    "target_url": target_url
                }
            }
        }

        try:
            response = requests.post(
                f"{self.authentication_config.api_url}/tyk/apis",
                json=payload,
                headers={
                    "Authorization": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Tyk API error: {e}")

        self.logger.info(f"Tyk API created: {api_name}")
        return {"status": "success", "api_name": api_name}
