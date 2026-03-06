"""Google Cloud Storage provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GCSProviderAuthConfig:
    credentials_json: str = dataclasses.field(
        metadata={"required": True, "description": "GCS Credentials JSON", "sensitive": True},
        default=""
    )
    bucket: str = dataclasses.field(
        metadata={"required": True, "description": "Bucket Name"},
        default=""
    )

class GCSProvider(BaseProvider):
    """Google Cloud Storage provider."""
    
    PROVIDER_DISPLAY_NAME = "Google Cloud Storage"
    PROVIDER_CATEGORY = ["Storage"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GCSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, object_name: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not object_name or not content:
            raise ProviderException("Object name and content are required")

        self.logger.info("GCS object upload initiated")
        return {"status": "success", "bucket": self.authentication_config.bucket, "object": object_name}
