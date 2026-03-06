"""WooCommerce e-commerce provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WooCommerceProviderAuthConfig:
    consumer_key: str = dataclasses.field(
        metadata={"required": True, "description": "WooCommerce Consumer Key"},
        default=""
    )
    consumer_secret: str = dataclasses.field(
        metadata={"required": True, "description": "WooCommerce Consumer Secret", "sensitive": True},
        default=""
    )
    store_url: str = dataclasses.field(
        metadata={"required": True, "description": "WooCommerce Store URL"},
        default=""
    )

class WooCommerceProvider(BaseProvider):
    """WooCommerce e-commerce provider."""
    
    PROVIDER_DISPLAY_NAME = "WooCommerce"
    PROVIDER_CATEGORY = ["E-commerce & Retail"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.store_url = self.authentication_config.store_url
        self.api_url = f"{self.store_url}/wp-json/wc/v3"

    def validate_config(self):
        self.authentication_config = WooCommerceProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, endpoint: str = "", data: dict = None, **kwargs: Dict[str, Any]):
        if not endpoint or not data:
            raise ProviderException("Endpoint and data are required")

        try:
            response = requests.post(
                f"{self.api_url}/{endpoint}",
                json=data,
                auth=(self.authentication_config.consumer_key, self.authentication_config.consumer_secret),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"WooCommerce API error: {e}")

        self.logger.info(f"WooCommerce API called: {endpoint}")
        return {"status": "success", "endpoint": endpoint}
