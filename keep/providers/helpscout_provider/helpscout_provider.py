"""Help Scout help desk provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HelpScoutProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Help Scout Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Help Scout Client Secret", "sensitive": True},
        default=""
    )

class HelpScoutProvider(BaseProvider):
    """Help Scout help desk provider."""
    
    PROVIDER_DISPLAY_NAME = "Help Scout"
    PROVIDER_CATEGORY = ["Customer Support"]
    HELPSCOUT_API = "https://api.helpscout.net/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HelpScoutProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, mailbox_id: str = "", subject: str = "", body: str = "", customer_email: str = "", **kwargs: Dict[str, Any]):
        if not mailbox_id or not subject or not customer_email:
            raise ProviderException("Mailbox ID, subject, and customer email are required")

        payload = {
            "subject": subject,
            "mailboxId": mailbox_id,
            "customer": {"email": customer_email},
            "threads": [{
                "type": "customer",
                "customer": {"email": customer_email},
                "text": body
            }]
        }

        try:
            response = requests.post(
                f"{self.HELPSCOUT_API}/conversations",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.client_secret}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Help Scout API error: {e}")

        self.logger.info(f"Help Scout conversation created: {subject}")
        return {"status": "success", "subject": subject}
