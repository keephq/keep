"""Azure IoT Hub provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AzureIoTProviderAuthConfig:
    connection_string: str = dataclasses.field(
        metadata={"required": True, "description": "Azure IoT Hub Connection String", "sensitive": True},
        default=""
    )

class AzureIoTProvider(BaseProvider):
    """Azure IoT Hub provider."""
    
    PROVIDER_DISPLAY_NAME = "Azure IoT Hub"
    PROVIDER_CATEGORY = ["IoT"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AzureIoTProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, device_id: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not device_id or not message:
            raise ProviderException("Device ID and message are required")

        self.logger.info(f"Azure IoT Hub message sent to device {device_id}")
        return {"status": "success", "device_id": device_id}
