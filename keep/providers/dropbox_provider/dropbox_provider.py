"""Dropbox storage provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DropboxProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Dropbox Access Token", "sensitive": True},
        default=""
    )

class DropboxProvider(BaseProvider):
    """Dropbox storage provider."""
    
    PROVIDER_DISPLAY_NAME = "Dropbox"
    PROVIDER_CATEGORY = ["Storage"]
    DROPBOX_API = "https://content.dropboxapi.com/2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DropboxProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, path: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not path or not content:
            raise ProviderException("Path and content are required")

        try:
            response = requests.post(
                f"{self.DROPBOX_API}/files/upload",
                data=content.encode(),
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Dropbox-API-Arg": f"{{\"path\": \"{path}\"}}"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Dropbox API error: {e}")

        self.logger.info("Dropbox file uploaded")
        return {"status": "success", "path": path}
