"""Shopify e-commerce provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ShopifyProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Shopify Access Token", "sensitive": True},
        default=""
    )

    shop_domain: str = dataclasses.field(
        metadata={"required": True, "description": "Shopify Store Domain"},
        default=""
    )

class ShopifyProvider(BaseProvider):
    """Shopify e-commerce provider."""
    
    PROVIDER_DISPLAY_NAME = "Shopify"
    PROVIDER_CATEGORY = ["E-commerce & Retail"]
    SHOPIFY_API = "https://{shop_domain}.myshopify.com/admin/api"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.shop_domain = self.authentication_config.shop_domain

        self.api_url = self.SHOPIFY_API.format(shop_domain=self.shop_domain)

    def validate_config(self):
        self.authentication_config = ShopifyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, product_id: str = "", title: str = "", **kwargs: Dict[str, Any]):
        if not product_id or not title:
            raise ProviderException("Product ID and title are required")

        payload = {
            "product": {
                "title": title,
                "body_html": kwargs.get("description", ""),
                "vendor": kwargs.get("vendor", "Keep"),
                "product_type": kwargs.get("product_type", "simple")
            }
        }

        try:
            response = requests.post(
                f"{self.api_url}/products.json",
                json=payload,
                headers={"X-Shopify-Access-Token": self.authentication_config.access_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Shopify API error: {e}")

        self.logger.info(f"Shopify product created: {product_id}")
        return {"status": "success", "product_id": product_id}
