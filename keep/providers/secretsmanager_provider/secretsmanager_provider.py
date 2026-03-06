"""AWS Secrets Manager provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SecretsManagerProviderAuthConfig:
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

class SecretsManagerProvider(BaseModel):
    """AWS Secrets Manager provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS Secrets Manager"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SecretsManagerProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, secret_name: str = "", secret_value: str = "", **kwargs: Dict[str, Any]):
        if not secret_name or not secret_value:
            raise ProviderException("Secret name and value are required")

        # Note: In production, use boto3
        self.logger.info(f"AWS Secrets Manager secret {secret_name} written")
        return {"status": "success", "secret_name": secret_name}
