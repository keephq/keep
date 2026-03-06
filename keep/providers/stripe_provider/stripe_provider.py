"""Stripe payment provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class StripeProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Stripe API Key", "sensitive": True},
        default=""
    )

class StripeProvider(BaseProvider):
    """Stripe payment provider."""
    
    PROVIDER_DISPLAY_NAME = "Stripe"
    PROVIDER_CATEGORY = ["Payments"]
    STRIPE_API = "https://api.stripe.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = StripeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, amount: int = "", currency: str = "usd", **kwargs: Dict[str, Any]):
        if not amount:
            raise ProviderException("Amount is required")

        try:
            response = requests.post(
                f"{self.STRIPE_API}/payment_intents",
                data={"amount": amount, "currency": currency},
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Stripe API error: {e}")

        self.logger.info("Stripe payment intent created")
        return {"status": "success", "id": response.json().get("id")}
