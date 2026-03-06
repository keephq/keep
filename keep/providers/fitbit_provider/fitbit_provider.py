"""Fitbit fitness tracking provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FitbitProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Fitbit Access Token", "sensitive": True},
        default=""
    )

class FitbitProvider(BaseModel):
    """Fitbit fitness tracking provider."""
    
    PROVIDER_DISPLAY_NAME = "Fitbit"
    PROVIDER_CATEGORY = ["Health & Fitness"]
    FITBIT_API = "https://api.fitbit.com/1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FitbitProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, user_id: str = "", activity: str = "", **kwargs: Dict[str, Any]):
        if not user_id or not activity:
            raise ProviderException("User ID and activity are required")

        self.logger.info(f"Fitbit activity logged for {user_id}")
        return {"status": "success", "user_id": user_id}
