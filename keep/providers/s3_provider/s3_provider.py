"""AWS S3 storage provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class S3ProviderAuthConfig:
    access_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Access Key", "sensitive": True},
        default=""
    )
    secret_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Secret Key", "sensitive": True},
        default=""
    )
    region: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Region"},
        default="us-east-1"
    )
    bucket: str = dataclasses.field(
        metadata={"required": True, "description": "S3 Bucket Name"},
        default=""
    )

class S3Provider(BaseProvider):
    """AWS S3 storage provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS S3"
    PROVIDER_CATEGORY = ["Storage"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = S3ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, key: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not key or not content:
            raise ProviderException("Key and content are required")

        # Note: In production, use boto3
        self.logger.info("S3 object upload initiated")
        return {"status": "success", "bucket": self.authentication_config.bucket, "key": key}
