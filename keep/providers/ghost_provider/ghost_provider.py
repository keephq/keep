"""Ghost CMS content management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GhostCMSProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Ghost CMS API Key", "sensitive": True},
        default=""
    )
    admin_api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Ghost CMS Admin API Key", "sensitive": True},
        default=""
    )

class GhostCMSProvider(BaseProvider):
    """Ghost CMS content management provider."""
    
    PROVIDER_DISPLAY_NAME = "Ghost CMS"
    PROVIDER_CATEGORY = ["Content Management"]
    GHOST_API = "https://api.ghost.org/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GhostCMSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, post_id: str = "", title: str = "", **kwargs: Dict[str, Any]):
        if not title:
            raise ProviderException("Title is required")

        payload = {
            "posts": [{
                "title": title,
                "html": kwargs.get("content", "")
            }]
        }

        try:
            response = requests.post(
                f"{self.GHOST_API}/content/posts/",
                json=payload,
                headers={
                    "Authorization": f"Ghost {self.authentication_config.admin_api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Ghost CMS API error: {e}")

        self.logger.info(f"Ghost CMS post created: {title}")
        return {"status": "success", "title": title}
