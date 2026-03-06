"""Netlify hosting provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NetlifyProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Netlify Access Token", "sensitive": True},
        default=""
    )
    site_id: str = dataclasses.field(
        metadata={"required": True, "description": "Netlify Site ID"},
        default=""
    )

class NetlifyProvider(BaseProvider):
    """Netlify hosting provider."""
    
    PROVIDER_DISPLAY_NAME = "Netlify"
    PROVIDER_CATEGORY = ["Web Hosting"]
    NETLIFY_API = "https://api.netlify.com/api/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NetlifyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not title:
            raise ProviderException("Title is required")

        payload = {
            "title": title,
            "message": message,
            "site_id": self.authentication_config.site_id
        }

        try:
            response = requests.post(
                f"{self.NETLIFY_API}/deploys",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Netlify API error: {e}")

        self.logger.info(f"Netlify deploy triggered: {title}")
        return {"status": "success", "title": title}
