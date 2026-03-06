"""Vimeo video hosting provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VimeoProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Vimeo Access Token", "sensitive": True},
        default=""
    )

class VimeoProvider(BaseProvider):
    """Vimeo video hosting provider."""
    
    PROVIDER_DISPLAY_NAME = "Vimeo"
    PROVIDER_CATEGORY = ["Social Media"]
    VIMEO_API = "https://api.vimeo.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VimeoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, video_id: str = "", title: str = "", description: str = "", **kwargs: Dict[str, Any]):
        if not video_id:
            raise ProviderException("Video ID is required")

        try:
            response = requests.patch(
                f"{self.VIMEO_API}/videos/{video_id}",
                json={"name": title, "description": description},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Vimeo API error: {e}")

        self.logger.info(f"Vimeo video {video_id} updated")
        return {"status": "success", "video_id": video_id}
