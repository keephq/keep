"""BigCommerce e-commerce provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BigCommerceProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "BigCommerce Access Token", "sensitive": True},
        default=""
    )
    store_hash: str = dataclasses.field(
        metadata={"required": True, "description": "BigCommerce Store Hash"},
        default=""
    )

class BigCommerceProvider(BaseProvider):
    """BigCommerce e-commerce provider."""
    
    PROVIDER_DISPLAY_NAME = "BigCommerce"
    PROVIDER_CATEGORY = ["E-commerce & Retail"]
    BIGCOMMERCE_API = "https://api.bigcommerce.com/stores"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BigCommerceProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, endpoint: str = "", data: dict = None, **kwargs: Dict[str, Any]):
        if not endpoint or not data:
            raise ProviderException("Endpoint and data are required")

        try:
            response = requests.post(
                f"{self.BIGCOMMERCE_API}/{self.authentication_config.store_hash}/v3/{endpoint}",
                json=data,
                headers={
                    "X-Auth-Token": self.authentication_config.access_token,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"BigCommerce API error: {e}")

        self.logger.info(f"BigCommerce API called: {endpoint}")
        return {"status": "success", "endpoint": endpoint}
