"""Braintree payment provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BraintreeProviderAuthConfig:
    merchant_id: str = dataclasses.field(
        metadata={"required": True, "description": "Braintree Merchant ID"},
        default=""
    )
    public_key: str = dataclasses.field(
        metadata={"required": True, "description": "Braintree Public Key"},
        default=""
    )
    private_key: str = dataclasses.field(
        metadata={"required": True, "description": "Braintree Private Key", "sensitive": True},
        default=""
    )

class BraintreeProvider(BaseProvider):
    """Braintree payment provider."""
    
    PROVIDER_DISPLAY_NAME = "Braintree"
    PROVIDER_CATEGORY = ["Payments"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BraintreeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, amount: str = "", **kwargs: Dict[str, Any]):
        if not amount:
            raise ProviderException("Amount is required")

        # Note: In production, use braintree SDK
        self.logger.info("Braintree transaction initiated")
        return {"status": "success", "amount": amount}
