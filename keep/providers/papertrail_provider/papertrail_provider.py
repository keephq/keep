"""Papertrail logging provider."""

import dataclasses
import socket
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PapertrailProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Papertrail Host"},
        default=""
    )
    port: int = dataclasses.field(
        metadata={"required": True, "description": "Papertrail Port"},
        default=12345
    )

class PapertrailProvider(BaseProvider):
    """Papertrail logging provider."""
    
    PROVIDER_DISPLAY_NAME = "Papertrail"
    PROVIDER_CATEGORY = ["Logging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PapertrailProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(message.encode(), (self.authentication_config.host, self.authentication_config.port))
            sock.close()
        except Exception as e:
            raise ProviderException(f"Papertrail error: {e}")

        self.logger.info("Papertrail log sent")
        return {"status": "success"}
