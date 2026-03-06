"""Glip team messaging provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class GlipProviderAuthConfig:
    webhook_url: str = dataclasses.field(metadata={"required": True, "description": "Glip Webhook URL", "sensitive": True}, default="")

class GlipProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Glip"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GlipProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, text: str = "", **kwargs: Dict[str, Any]):
        if not text:
            raise ProviderException("Text is required")
        payload = {"text": text}
        try:
            response = requests.post(self.authentication_config.webhook_url, json=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Glip API error: {e}")
        self.logger.info("Glip message sent")
        return {"status": "success"}
