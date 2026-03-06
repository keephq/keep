"""SignalWire Voice provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SignalWireProviderAuthConfig:
    account_sid: str = dataclasses.field(
        metadata={"required": True, "description": "SignalWire Account SID"},
        default=""
    )
    auth_token: str = dataclasses.field(
        metadata={"required": True, "description": "SignalWire Auth Token", "sensitive": True},
        default=""
    )
    space_url: str = dataclasses.field(
        metadata={"required": True, "description": "SignalWire Space URL"},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class SignalWireProvider(BaseProvider):
    """SignalWire Voice provider."""
    
    PROVIDER_DISPLAY_NAME = "SignalWire"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["voice", "phone"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SignalWireProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        url = f"https://{self.authentication_config.space_url}/api/laml/2010-04-01/Accounts/{self.authentication_config.account_sid}/Calls.json"
        
        twiml = f"<Response><Say>{message}</Say></Response>"
        
        data = {
            "From": self.authentication_config.from_number,
            "To": to,
            "Twiml": twiml
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
            raise ProviderException(f"SignalWire API error: {e}")

        self.logger.info("Phone call initiated via SignalWire")
        return {"status": "success"}
