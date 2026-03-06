"""Zoom meeting provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ZoomProviderAuthConfig:
    jwt_token: str = dataclasses.field(
        metadata={"required": True, "description": "Zoom JWT Token", "sensitive": True},
        default=""
    )

class ZoomProvider(BaseProvider):
    """Zoom meeting provider."""
    
    PROVIDER_DISPLAY_NAME = "Zoom"
    PROVIDER_CATEGORY = ["Collaboration"]
    ZOOM_API = "https://api.zoom.us/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZoomProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, topic: str = "", duration: int = 30, **kwargs: Dict[str, Any]):
        if not topic:
            raise ProviderException("Topic is required")

        payload = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "duration": duration
        }

        try:
            response = requests.post(
                f"{self.ZOOM_API}/users/me/meetings",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.jwt_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Zoom API error: {e}")

        self.logger.info("Zoom meeting created")
        return response.json()
