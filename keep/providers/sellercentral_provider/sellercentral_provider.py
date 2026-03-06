"""Amazon Seller Central provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SellerCentralProviderAuthConfig:
    refresh_token: str = dataclasses.field(
        metadata={"required": True, "description": "Amazon Seller Central Refresh Token", "sensitive": True},
        default=""
    )
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Amazon Seller Central Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Amazon Seller Central Client Secret", "sensitive": True},
        default=""
    )

class SellerCentralProvider(BaseProvider):
    """Amazon Seller Central provider."""
    
    PROVIDER_DISPLAY_NAME = "Amazon Seller Central"
    PROVIDER_CATEGORY = ["E-commerce & Retail"]
    SELLER_API = "https://sellingpartnerapi-na.amazon.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SellerCentralProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, endpoint: str = "", data: dict = None, **kwargs: Dict[str, Any]):
        if not endpoint or not data:
            raise ProviderException("Endpoint and data are required")

        try:
            response = requests.post(
                f"{self.SELLER_API}{endpoint}",
                json=data,
                headers={
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Amazon Seller Central API error: {e}")

        self.logger.info(f"Amazon Seller Central API called: {endpoint}")
        return {"status": "success", "endpoint": endpoint}
