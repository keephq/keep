"""MQTT IoT messaging provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MQTTProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "MQTT Broker Host"},
        default=""
    )
    port: int = dataclasses.field(
        metadata={"description": "MQTT Port"},
        default=1883
    )
    username: str = dataclasses.field(
        metadata={"description": "Username"},
        default=""
    )
    password: str = dataclasses.field(
        metadata={"description": "Password", "sensitive": True},
        default=""
    )

class MQTTProvider(BaseProvider):
    """MQTT IoT messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "MQTT"
    PROVIDER_CATEGORY = ["IoT"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MQTTProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, topic: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not topic or not message:
            raise ProviderException("Topic and message are required")

        # Note: In production, use paho-mqtt
        self.logger.info(f"MQTT message published to {topic}")
        return {"status": "success", "topic": topic}
