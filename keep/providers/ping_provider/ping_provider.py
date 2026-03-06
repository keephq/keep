"""Ping Identity provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PingProviderAuthConfig:
    environment_id: str = dataclasses.field(
        metadata={"required": True, "description": "Ping Environment ID"},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Ping Access Token", "sensitive": True},
        default=""
    )

class PingProvider(BaseModel):
    """Ping Identity provider."""
    
    PROVIDER_DISPLAY_NAME = "Ping Identity"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PingProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, user_id: str = "", **kwargs: Dict[str, Any]):
        if not user_id:
            raise ProviderException("User ID is required")

        self.logger.info(f"Ping Identity action for user {user_id}")
        return {"status": "success", "user_id": user_id}
