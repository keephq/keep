"""FireHydrant incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FireHydrantProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "FireHydrant API Key", "sensitive": True},
        default=""
    )

class FireHydrantProvider(BaseProvider):
    """FireHydrant incident management provider."""
    
    PROVIDER_DISPLAY_NAME = "FireHydrant"
    PROVIDER_CATEGORY = ["Incident Management"]
    FIREHYDRANT_API = "https://api.firehydrant.io/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FireHydrantProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, name: str = "", summary: str = "", **kwargs: Dict[str, Any]):
        if not name:
            raise ProviderException("Incident name is required")

        payload = {
            "incident": {
                "name": name,
                "summary": summary or name
            }
        }

        try:
            response = requests.post(
                f"{self.FIREHYDRANT_API}/incidents",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"FireHydrant API error: {e}")

        self.logger.info("FireHydrant incident created")
        return {"status": "success"}
