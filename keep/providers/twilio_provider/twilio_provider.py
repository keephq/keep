"""Twilio SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TwilioProviderAuthConfig:
    account_sid: str = dataclasses.field(
        metadata={"required": True, "description": "Twilio Account SID", "sensitive": True},
        default=""
    )
    auth_token: str = dataclasses.field(
        metadata={"required": True, "description": "Twilio Auth Token", "sensitive": True},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "Twilio Phone Number"},
        default=""
    )

class TwilioProvider(BaseProvider):
    """Twilio SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Twilio"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    
    TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TwilioProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        url = f"{self.TWILIO_API}/{self.authentication_config.account_sid}/Messages.json"
        
        data = {
            "From": self.authentication_config.from_number,
            "To": to,
            "Body": message
        }

        try:
            response = requests.post(
                url,
                data=data,
                auth=(self.authentication_config.account_sid, self.authentication_config.auth_token),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Twilio API error: {e}")

        self.logger.info("SMS sent via Twilio")
        return {"status": "success"}
