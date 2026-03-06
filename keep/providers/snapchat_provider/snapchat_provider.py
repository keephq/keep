"""Snapchat social media provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnapchatProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Snapchat Access Token", "sensitive": True},
        default=""
    )

class SnapchatProvider(BaseProvider):
    """Snapchat social media provider."""
    
    PROVIDER_DISPLAY_NAME = "Snapchat"
    PROVIDER_CATEGORY = ["Social Media"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SnapchatProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, snap_id: str = "", caption: str = "", **kwargs: Dict[str, Any]):
        if not snap_id:
            raise ProviderException("Snap ID is required")

        self.logger.info(f"Snapchat snap {snap_id} processed")
        return {"status": "success", "snap_id": snap_id}
