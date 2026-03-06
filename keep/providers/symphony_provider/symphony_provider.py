"""Symphony messaging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SymphonyProviderAuthConfig:
    api_url: str = dataclasses.field(
        metadata={"required": True, "description": "Symphony API URL"},
        default=""
    )
    session_token: str = dataclasses.field(
        metadata={"required": True, "description": "Symphony Session Token", "sensitive": True},
        default=""
    )
    stream_id: str = dataclasses.field(
        metadata={"required": True, "description": "Symphony Stream ID"},
        default=""
    )

class SymphonyProvider(BaseProvider):
    """Symphony messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Symphony"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SymphonyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {"message": f"<messageML>{message}</messageML>"}

        try:
            response = requests.post(
                f"{self.authentication_config.api_url}/v4/stream/{self.authentication_config.stream_id}/message/create",
                json=payload,
                headers={"sessionToken": self.authentication_config.session_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Symphony API error: {e}")

        self.logger.info("Symphony message sent")
        return {"status": "success"}
