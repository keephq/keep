"""Box storage provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BoxProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Box Access Token", "sensitive": True},
        default=""
    )

class BoxProvider(BaseModel):
    """Box storage provider."""
    
    PROVIDER_DISPLAY_NAME = "Box"
    PROVIDER_CATEGORY = ["Storage"]
    BOX_API = "https://api.box.com/2.0"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BoxProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, parent_id: str = "0", name: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not name or not content:
            raise ProviderException("Name and content are required")

        try:
            response = requests.post(
                f"{self.BOX_API}/files/content",
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Box API error: {e}")

        self.logger.info("Box file uploaded")
        return {"status": "success", "name": name}
