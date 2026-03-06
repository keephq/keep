"""Magento e-commerce provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MagentoProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Magento Access Token", "sensitive": True},
        default=""
    )
    store_url: str = dataclasses.field(
        metadata={"required": True, "description": "Magento Store URL"},
        default=""
    )

class MagentoProvider(BaseProvider):
    """Magento e-commerce provider."""
    
    PROVIDER_DISPLAY_NAME = "Magento"
    PROVIDER_CATEGORY = ["E-commerce & Retail"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.store_url = self.authentication_config.store_url

    def validate_config(self):
        self.authentication_config = MagentoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, endpoint: str = "", data: dict = None, **kwargs: Dict[str, Any]):
        if not endpoint or not data:
            raise ProviderException("Endpoint and data are required")

        try:
            response = requests.post(
                f"{self.store_url}/rest/V1/{endpoint}",
                json=data,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Magento API error: {e}")

        self.logger.info(f"Magento API called: {endpoint}")
        return {"status": "success", "endpoint": endpoint}
