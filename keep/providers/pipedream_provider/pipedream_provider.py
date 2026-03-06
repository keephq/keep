"""Pipedream integration platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PipedreamProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Pipedream Webhook URL", "sensitive": True},
        default=""
    )

class PipedreamProvider(BaseProvider):
    """Pipedream integration platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Pipedream"
    PROVIDER_CATEGORY = ["Automation"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PipedreamProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "message": message,
            **kwargs
        }

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Pipedream API error: {e}")

        self.logger.info(f"Pipedream webhook triggered")
        return {"status": "success"}
