"""xMatters incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class XMattersProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "xMatters Webhook URL", "sensitive": True},
        default=""
    )

class XMattersProvider(BaseProvider):
    """xMatters incident provider."""
    
    PROVIDER_DISPLAY_NAME = "xMatters"
    PROVIDER_CATEGORY = ["Incident Management"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = XMattersProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", priority: str = "High", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "message": message,
            "priority": priority
        }

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"xMatters API error: {e}")

        self.logger.info("xMatters incident created")
        return {"status": "success"}
