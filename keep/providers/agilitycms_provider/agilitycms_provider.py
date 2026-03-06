"""Agility CMS headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AgilityCMSProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Agility CMS API Key", "sensitive": True},
        default=""
    )
    instance_id: str = dataclasses.field(
        metadata={"required": True, "description": "Agility CMS Instance ID"},
        default=""
    )

class AgilityCMSProvider(BaseModel):
    """Agility CMS headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Agility CMS"
    PROVIDER_CATEGORY = ["Content Management"]
    AGILITY_API = "https://api.aglty.io"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AgilityCMSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, reference_name: str = "", content_id: str = "", fields: dict = None, **kwargs: Dict[str, Any]):
        if not reference_name or not content_id:
            raise ProviderException("Reference name and content ID are required")

        payload = {
            "fields": fields or {}
        }

        try:
            response = requests.post(
                f"{self.AGILITY_API}/{self.authentication_config.instance_id}/en-us/item/{content_id}",
                json=payload,
                headers={
                    "APIKey": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Agility CMS API error: {e}")

        self.logger.info(f"Agility CMS content updated: {reference_name}")
        return {"status": "success", "reference_name": reference_name}
