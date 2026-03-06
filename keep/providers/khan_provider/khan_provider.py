"""Khan Academy education provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class KhanProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Khan Academy API Key", "sensitive": True},
        default=""
    )

class KhanProvider(BaseModel):
    """Khan Academy education provider."""
    
    PROVIDER_DISPLAY_NAME = "Khan Academy"
    PROVIDER_CATEGORY = ["Education"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = KhanProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, user_id: str = "", lesson: str = "", **kwargs: Dict[str, Any]):
        if not user_id or not lesson:
            raise ProviderException("User ID and lesson are required")

        self.logger.info(f"Khan Academy lesson completed for {user_id}")
        return {"status": "success", "user_id": user_id}
