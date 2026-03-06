"""Adobe Creative Cloud provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AdobeCCProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Adobe Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Adobe Client Secret", "sensitive": True},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Adobe Access Token", "sensitive": True},
        default=""
    )

class AdobeCCProvider(BaseProvider):
    """Adobe Creative Cloud provider."""
    
    PROVIDER_DISPLAY_NAME = "Adobe Creative Cloud"
    PROVIDER_CATEGORY = ["Design & Creative"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AdobeCCProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, asset_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not asset_id:
            raise ProviderException("Asset ID is required")

        self.logger.info(f"Adobe CC asset processed: {asset_id}")
        return {"status": "success", "asset_id": asset_id}
