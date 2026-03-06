"""TikTok social media provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TikTokProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "TikTok Access Token", "sensitive": True},
        default=""
    )

class TikTokProvider(BaseProvider):
    """TikTok social media provider."""
    
    PROVIDER_DISPLAY_NAME = "TikTok"
    PROVIDER_CATEGORY = ["Social Media"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TikTokProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, video_id: str = "", caption: str = "", **kwargs: Dict[str, Any]):
        if not video_id:
            raise ProviderException("Video ID is required")

        self.logger.info(f"TikTok video {video_id} processed")
        return {"status": "success", "video_id": video_id}
