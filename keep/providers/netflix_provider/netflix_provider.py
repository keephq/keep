"""Netflix streaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NetflixProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Netflix API Key", "sensitive": True},
        default=""
    )

class NetflixProvider(BaseModel):
    """Netflix streaming provider."""
    
    PROVIDER_DISPLAY_NAME = "Netflix"
    PROVIDER_CATEGORY = ["Media & Entertainment"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NetflixProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, profile_id: str = "", title_id: str = "", **kwargs: Dict[str, Any]):
        if not profile_id or not title_id:
            raise ProviderException("Profile ID and title ID are required")

        self.logger.info(f"Netflix title {title_id} added to list for {profile_id}")
        return {"status": "success", "profile_id": profile_id}
