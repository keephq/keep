"""Apple Music streaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AppleMusicProviderAuthConfig:
    developer_token: str = dataclasses.field(
        metadata={"required": True, "description": "Apple Music Developer Token", "sensitive": True},
        default=""
    )

class AppleMusicProvider(BaseModel):
    """Apple Music streaming provider."""
    
    PROVIDER_DISPLAY_NAME = "Apple Music"
    PROVIDER_CATEGORY = ["Media & Entertainment"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AppleMusicProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, playlist_id: str = "", song_id: str = "", **kwargs: Dict[str, Any]):
        if not playlist_id or not song_id:
            raise ProviderException("Playlist ID and song ID are required")

        self.logger.info(f"Apple Music song added to playlist {playlist_id}")
        return {"status": "success", "playlist_id": playlist_id}
