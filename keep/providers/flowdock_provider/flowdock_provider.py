"""Flowdock provider for team messaging."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FlowdockProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Flowdock API Token", "sensitive": True},
        default=""
    )
    flow_id: str = dataclasses.field(
        metadata={"required": True, "description": "Flowdock Flow ID"},
        default=""
    )

class FlowdockProvider(BaseProvider):
    """Flowdock team messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Flowdock"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]
    FLOWDOCK_API = "https://api.flowdock.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FlowdockProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "event": "message",
            "content": message
        }

        try:
            response = requests.post(
                f"{self.FLOWDOCK_API}/flows/{self.authentication_config.flow_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Flowdock API error: {e}")

        self.logger.info("Flowdock message sent")
        return {"status": "success"}
