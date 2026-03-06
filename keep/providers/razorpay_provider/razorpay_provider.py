"""Razorpay payment provider (India market)."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RazorpayProviderAuthConfig:
    key_id: str = dataclasses.field(
        metadata={"required": True, "description": "Razorpay Key ID"},
        default=""
    )
    key_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Razorpay Key Secret", "sensitive": True},
        default=""
    )

class RazorpayProvider(BaseProvider):
    """Razorpay payment provider for India market."""
    
    PROVIDER_DISPLAY_NAME = "Razorpay"
    PROVIDER_CATEGORY = ["Payments"]
    RAZORPAY_API = "https://api.razorpay.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RazorpayProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, amount: int = "", currency: str = "INR", **kwargs: Dict[str, Any]):
        if not amount:
            raise ProviderException("Amount is required")

        payload = {
            "amount": amount,
            "currency": currency,
            "payment_capture": 1
        }

        try:
            response = requests.post(
                f"{self.RAZORPAY_API}/orders",
                json=payload,
                auth=(self.authentication_config.key_id, self.authentication_config.key_secret),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Razorpay API error: {e}")

        self.logger.info("Razorpay order created")
        return {"status": "success", "id": response.json().get("id")}
