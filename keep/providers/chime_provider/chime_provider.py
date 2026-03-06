"""Amazon Chime provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ChimeProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Chime Webhook URL", "sensitive": True},
        default=""
    )

class ChimeProvider(BaseProvider):
    """Amazon Chime messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Amazon Chime"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ChimeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content: str = "", **kwargs: Dict[str, Any]):
        if not content:
            raise ProviderException("Content is required")

        payload = {"Content": content}

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Chime API error: {e}")

        self.logger.info("Chime message sent")
        return {"status": "success"}
