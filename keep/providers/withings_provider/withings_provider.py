"""Withings health tracking provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WithingsProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Withings Access Token", "sensitive": True},
        default=""
    )

class WithingsProvider(BaseModel):
    """Withings health tracking provider."""
    
    PROVIDER_DISPLAY_NAME = "Withings"
    PROVIDER_CATEGORY = ["Health & Fitness"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WithingsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, user_id: str = "", measurement: str = "", **kwargs: Dict[str, Any]):
        if not user_id or not measurement:
            raise ProviderException("User ID and measurement are required")

        self.logger.info(f"Withings measurement logged for {user_id}")
        return {"status": "success", "user_id": user_id}
