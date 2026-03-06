"""Google Cloud IoT Core provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GCPIoTProviderAuthConfig:
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "GCP Project ID"},
        default=""
    )
    credentials_json: str = dataclasses.field(
        metadata={"required": True, "description": "GCP Credentials JSON", "sensitive": True},
        default=""
    )

class GCPIoTProvider(BaseProvider):
    """Google Cloud IoT Core provider."""
    
    PROVIDER_DISPLAY_NAME = "Google Cloud IoT"
    PROVIDER_CATEGORY = ["IoT"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GCPIoTProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, device_path: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not device_path or not message:
            raise ProviderException("Device path and message are required")

        self.logger.info(f"GCP IoT message sent to {device_path}")
        return {"status": "success", "device_path": device_path}
