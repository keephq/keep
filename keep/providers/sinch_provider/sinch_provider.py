"""Sinch SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SinchProviderAuthConfig:
    service_plan_id: str = dataclasses.field(
        metadata={"required": True, "description": "Sinch Service Plan ID"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Sinch API Token", "sensitive": True},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class SinchProvider(BaseProvider):
    """Sinch SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Sinch"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    SINCH_API = "https://us.sms.api.sinch.com/xms/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SinchProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not to or not body:
            raise ProviderException("To and body are required")

        payload = {
            "from": self.authentication_config.from_number,
            "to": [to],
            "body": body
        }

        try:
            response = requests.post(
                f"{self.SINCH_API}/{self.authentication_config.service_plan_id}/batches",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sinch API error: {e}")

        self.logger.info("SMS sent via Sinch")
        return {"status": "success"}
