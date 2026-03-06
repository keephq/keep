"""Sprout Social social media management provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class SproutSocialProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Sprout Social API Key", "sensitive": True},
        default=""
    )

class SproutSocialProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Sprout Social"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    SPROUTSOCIAL_API = "https://api.sproutsocial.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SproutSocialProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        try:
            response = requests.post(
                f"{self.SPROUTSOCIAL_API}/message",
                json={"message": message},
                headers={"X-API-Key": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sprout Social API error: {e}")

        self.logger.info(f"Sprout Social message sent")
        return {"status": "success"}
