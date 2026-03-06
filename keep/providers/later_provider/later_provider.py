"""Later media library provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class LaterProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Later API Key", "sensitive": True},
        default=""
    )

class LaterProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Later"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    LATER_API = "https://api.getlater.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LaterProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, media_id: str = "", **kwargs: Dict[str, Any]):
        if not media_id:
            raise ProviderException("Media ID is required")

        try:
            response = requests.get(
                f"{self.LATER_API}/media/{media_id}",
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Later API error: {e}")

        self.logger.info(f"Later media retrieved: {media_id}")
        return {"status": "success", "media_id": media_id}
