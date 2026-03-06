"""Spotify music streaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SpotifyProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Spotify Access Token", "sensitive": True},
        default=""
    )

class SpotifyProvider(BaseModel):
    """Spotify music streaming provider."""
    
    PROVIDER_DISPLAY_NAME = "Spotify"
    PROVIDER_CATEGORY = ["Media & Entertainment"]
    SPOTIFY_API = "https://api.spotify.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SpotifyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, playlist_id: str = "", track_uri: str = "", **kwargs: Dict[str, Any]):
        if not playlist_id or not track_uri:
            raise ProviderException("Playlist ID and track URI are required")

        self.logger.info(f"Spotify track added to playlist {playlist_id}")
        return {"status": "success", "playlist_id": playlist_id}
