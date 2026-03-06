"""Duolingo language learning provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DuolingoProviderAuthConfig:
    jwt_token: str = dataclasses.field(
        metadata={"required": True, "description": "Duolingo JWT Token", "sensitive": True},
        default=""
    )

class DuolingoProvider(BaseModel):
    """Duolingo language learning provider."""
    
    PROVIDER_DISPLAY_NAME = "Duolingo"
    PROVIDER_CATEGORY = ["Education"]
    DUOLINGO_API = "https://www.duolingo.com/api/1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DuolingoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, username: str = "", lesson: str = "", **kwargs: Dict[str, Any]):
        if not username or not lesson:
            raise ProviderException("Username and lesson are required")

        self.logger.info(f"Duolingo lesson completed for {username}")
        return {"status": "success", "username": username}
