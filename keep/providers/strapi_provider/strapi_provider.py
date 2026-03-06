"""Strapi headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class StrapiProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Strapi API Token", "sensitive": True},
        default=""
    )
    api_url: str = dataclasses.field(
        metadata={"required": True, "description": "Strapi API URL"},
        default=""
    )

class StrapiProvider(BaseProvider):
    """Strapi headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Strapi"
    PROVIDER_CATEGORY = ["Content Management"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = StrapiProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, collection: str = "", data: dict = None, **kwargs: Dict[str, Any]):
        if not collection or not data:
            raise ProviderException("Collection and data are required")

        try:
            response = requests.post(
                f"{self.authentication_config.api_url}/{collection}",
                json={"data": data},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Strapi API error: {e}")

        self.logger.info(f"Strapi entry created in {collection}")
        return {"status": "success", "collection": collection}
