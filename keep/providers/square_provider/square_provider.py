"""Square payment provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SquareProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Square Access Token", "sensitive": True},
        default=""
    )
    location_id: str = dataclasses.field(
        metadata={"required": True, "description": "Square Location ID"},
        default=""
    )
    sandbox: bool = dataclasses.field(
        metadata={"description": "Use Sandbox Environment"},
        default=True
    )

class SquareProvider(BaseProvider):
    """Square payment provider."""
    
    PROVIDER_DISPLAY_NAME = "Square"
    PROVIDER_CATEGORY = ["Payments"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SquareProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    @property
    def api_url(self):
        return "https://connect.squareupsandbox.com" if self.authentication_config.sandbox else "https://connect.squareup.com"

    def _notify(self, amount_money: Dict = None, **kwargs: Dict[str, Any]):
        if not amount_money:
            raise ProviderException("Amount money is required")

        payload = {
            "idempotency_key": str(hash(str(amount_money))),
            "amount_money": amount_money
        }

        try:
            response = requests.post(
                f"{self.api_url}/v2/payments",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Square API error: {e}")

        self.logger.info("Square payment created")
        return {"status": "success"}
