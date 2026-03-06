"""Slack provider with Block Kit support."""

import dataclasses
from typing import Dict, Any, List

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class Slack2ProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Slack Webhook URL", "sensitive": True},
        default=""
    )

class Slack2Provider(BaseProvider):
    """Slack provider with Block Kit support."""
    
    PROVIDER_DISPLAY_NAME = "Slack (Blocks)"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Slack2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, blocks: List = None, **kwargs: Dict[str, Any]):
        if not blocks:
            raise ProviderException("Blocks are required")

        payload = {"blocks": blocks}

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Slack API error: {e}")

        self.logger.info("Slack blocks sent")
        return {"status": "success"}
