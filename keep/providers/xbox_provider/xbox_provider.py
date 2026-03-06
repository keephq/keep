"""Xbox Live gaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class XboxProviderAuthConfig:
    xbl_token: str = dataclasses.field(
        metadata={"required": True, "description": "Xbox Live Token", "sensitive": True},
        default=""
    )

class XboxProvider(BaseModel):
    """Xbox Live gaming provider."""
    
    PROVIDER_DISPLAY_NAME = "Xbox Live"
    PROVIDER_CATEGORY = ["Gaming"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = XboxProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, gamertag: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not gamertag or not message:
            raise ProviderException("Gamertag and message are required")

        self.logger.info(f"Xbox notification for {gamertag}")
        return {"status": "success", "gamertag": gamertag}
