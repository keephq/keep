"""Buffer social media scheduling provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class BufferProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Buffer Access Token", "sensitive": True},
        default=""
    )

class BufferProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Buffer"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    BUFFER_API = "https://api.bufferapp.com/1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BufferProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, profile_id: str = "", text: str = "", **kwargs: Dict[str, Any]):
        if not profile_id or not text:
            raise ProviderException("Profile ID and text are required")

        try:
            response = requests.post(
                f"{self.BUFFER_API}/profiles/{profile_id}/updates/create",
                json={"text": {"text": text}},
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Buffer API error: {e}")

        self.logger.info(f"Buffer update sent to profile {profile_id}")
        return {"status": "success", "profile_id": profile_id}
