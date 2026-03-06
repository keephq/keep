"""n8n workflow automation provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class N8NProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "n8n Webhook URL", "sensitive": True},
        default=""
    )

class N8NProvider(BaseProvider):
    """n8n workflow automation provider."""
    
    PROVIDER_DISPLAY_NAME = "n8n"
    PROVIDER_CATEGORY = ["Automation"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = N8NProviderAuthConfig(**self.config.authentication)

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
            raise ProviderException(f"n8n API error: {e}")

        self.logger.info(f"n8n webhook triggered")
        return {"status": "success"}
