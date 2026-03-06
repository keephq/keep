"""PayPal payment provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PayPalProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "PayPal Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "PayPal Client Secret", "sensitive": True},
        default=""
    )
    sandbox: bool = dataclasses.field(
        metadata={"description": "Use Sandbox Environment"},
        default=True
    )

class PayPalProvider(BaseProvider):
    """PayPal payment provider."""
    
    PROVIDER_DISPLAY_NAME = "PayPal"
    PROVIDER_CATEGORY = ["Payments"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PayPalProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    @property
    def api_url(self):
        return "https://api-m.sandbox.paypal.com" if self.authentication_config.sandbox else "https://api-m.paypal.com"

    def _notify(self, amount: str = "", currency: str = "USD", **kwargs: Dict[str, Any]):
        if not amount:
            raise ProviderException("Amount is required")

        # Note: In production, get access token first
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": currency, "value": amount}
            }]
        }

        try:
            response = requests.post(
                f"{self.api_url}/v2/checkout/orders",
                json=payload,
                auth=(self.authentication_config.client_id, self.authentication_config.client_secret),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"PayPal API error: {e}")

        self.logger.info("PayPal order created")
        return {"status": "success", "id": response.json().get("id")}
