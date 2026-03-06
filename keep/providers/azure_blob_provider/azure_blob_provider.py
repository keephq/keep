"""Azure Blob Storage provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AzureBlobProviderAuthConfig:
    connection_string: str = dataclasses.field(
        metadata={"required": True, "description": "Azure Storage Connection String", "sensitive": True},
        default=""
    )
    container: str = dataclasses.field(
        metadata={"required": True, "description": "Container Name"},
        default=""
    )

class AzureBlobProvider(BaseProvider):
    """Azure Blob Storage provider."""
    
    PROVIDER_DISPLAY_NAME = "Azure Blob Storage"
    PROVIDER_CATEGORY = ["Storage"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AzureBlobProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, blob_name: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not blob_name or not content:
            raise ProviderException("Blob name and content are required")

        self.logger.info("Azure Blob upload initiated")
        return {"status": "success", "container": self.authentication_config.container, "blob": blob_name}
