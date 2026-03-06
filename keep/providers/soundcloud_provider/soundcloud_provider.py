"""SoundCloud music streaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SoundCloudProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "SoundCloud Client ID"},
        default=""
    )
    oauth_token: str = dataclasses.field(
        metadata={"required": True, "description": "SoundCloud OAuth Token", "sensitive": True},
        default=""
    )

class SoundCloudProvider(BaseModel):
    """SoundCloud music streaming provider."""
    
    PROVIDER_DISPLAY_NAME = "SoundCloud"
    PROVIDER_CATEGORY = ["Media & Entertainment"]
    SOUNDCLOUD_API = "https://api.soundcloud.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SoundCloudProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, track_id: str = "", playlist_id: str = "", **kwargs: Dict[str, Any]):
        if not track_id:
            raise ProviderException("Track ID is required")

        self.logger.info(f"SoundCloud track {track_id} processed")
        return {"status": "success", "track_id": track_id}
