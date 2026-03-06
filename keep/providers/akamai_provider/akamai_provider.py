"""Akamai CDN provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AkamaiProviderAuthConfig:
    client_token: str = dataclasses.field(
        metadata={"required": True, "description": "Akamai Client Token", "sensitive": True},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Akamai Client Secret", "sensitive": True},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Akamai Access Token", "sensitive": True},
        default=""
    )
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Akamai API Host"},
        default=""
    )

class AkamaiProvider(BaseProvider):
    """Akamai CDN provider."""
    
    PROVIDER_DISPLAY_NAME = "Akamai"
    PROVIDER_CATEGORY = ["Network Infrastructure"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AkamaiProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, cpcode: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not cpcode:
            raise ProviderException("CPCode is required")

        self.logger.info(f"Akamai CPCode processed: {cpcode}")
        return {"status": "success", "cpcode": cpcode}
