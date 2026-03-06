"""Auth0 authentication provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class Auth0ProviderAuthConfig:
    domain: str = dataclasses.field(
        metadata={"required": True, "description": "Auth0 Domain"},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Auth0 Access Token", "sensitive": True},
        default=""
    )

class Auth0Provider(BaseProvider):
    """Auth0 authentication provider."""
    
    PROVIDER_DISPLAY_NAME = "Auth0"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Auth0ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, user_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not user_id or not action:
            raise ProviderException("User ID and action are required")

        self.logger.info(f"Auth0 action {action} for user {user_id}")
        return {"status": "success", "user_id": user_id, "action": action}
