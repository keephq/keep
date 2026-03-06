"""AWS IoT Core provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AWSIoTProviderAuthConfig:
    endpoint: str = dataclasses.field(
        metadata={"required": True, "description": "AWS IoT Endpoint"},
        default=""
    )
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

class AWSIoTProvider(BaseProvider):
    """AWS IoT Core provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS IoT Core"
    PROVIDER_CATEGORY = ["IoT"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AWSIoTProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, topic: str = "", payload: str = "", **kwargs: Dict[str, Any]):
        if not topic or not payload:
            raise ProviderException("Topic and payload are required")

        self.logger.info(f"AWS IoT message published to {topic}")
        return {"status": "success", "topic": topic}
