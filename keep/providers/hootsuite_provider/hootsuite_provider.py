"""Hootsuite social media management provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class HootsuiteProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Hootsuite Access Token", "sensitive": True},
        default=""
    )

class HootsuiteProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Hootsuite"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    HOOTSUITE_API = "https://api.hootsuite.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HootsuiteProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, social_network: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not social_network or not message:
            raise ProviderException("Social network and message are required")

        try:
            response = requests.post(
                f"{self.HOOTSUITE_API}/messages",
                json={"socialNetwork": social_network, "text": message},
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Hootsuite API error: {e}")

        self.logger.info(f"Hootsuite message sent to {social_network}")
        return {"status": "success", "social_network": social_network}
