"""WeCom (企业微信) provider for team messaging."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WeComProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "WeCom Webhook URL", "sensitive": True},
        default=""
    )

class WeComProvider(BaseProvider):
    """WeCom (企业微信) team messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WeComProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content: str = "", **kwargs: Dict[str, Any]):
        if not content:
            raise ProviderException("Content is required")

        payload = {
            "msgtype": "text",
            "text": {"content": content}
        }

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"WeCom API error: {e}")

        self.logger.info("WeCom message sent")
        return {"status": "success"}
