"""ButterCMS headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ButterCMSProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "ButterCMS API Token", "sensitive": True},
        default=""
    )

class ButterCMSProvider(BaseProvider):
    """ButterCMS headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "ButterCMS"
    PROVIDER_CATEGORY = ["Content Management"]
    BUTTERCMS_API = "https://api.buttercms.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ButterCMSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content_type: str = "", title: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not content_type or not title:
            raise ProviderException("Content type and title are required")

        payload = {
            "title": title,
            "body": body
        }

        try:
            response = requests.post(
                f"{self.BUTTERCMS_API}/content/{content_type}/",
                json=payload,
                params={"auth_token": self.authentication_config.api_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"ButterCMS API error: {e}")

        self.logger.info(f"ButterCMS content created: {content_type}")
        return {"status": "success", "content_type": content_type}
