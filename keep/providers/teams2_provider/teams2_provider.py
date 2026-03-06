"""Teams provider with Adaptive Cards support."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class Teams2ProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Teams Webhook URL", "sensitive": True},
        default=""
    )

class Teams2Provider(BaseProvider):
    """Teams provider with Adaptive Cards support."""
    
    PROVIDER_DISPLAY_NAME = "Teams (Cards)"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Teams2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, card: Dict = None, **kwargs: Dict[str, Any]):
        if not card:
            raise ProviderException("Card is required")

        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card
            }]
        }

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Teams API error: {e}")

        self.logger.info("Teams card sent")
        return {"status": "success"}
