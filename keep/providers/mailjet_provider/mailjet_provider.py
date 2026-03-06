"""Mailjet Email provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MailjetProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Mailjet API Key", "sensitive": True},
        default=""
    )
    secret_key: str = dataclasses.field(
        metadata={"required": True, "description": "Mailjet Secret Key", "sensitive": True},
        default=""
    )
    from_email: str = dataclasses.field(
        metadata={"required": True, "description": "From Email Address"},
        default=""
    )

class MailjetProvider(BaseProvider):
    """Mailjet Email provider."""
    
    PROVIDER_DISPLAY_NAME = "Mailjet"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["email"]
    MAILJET_API = "https://api.mailjet.com/v3.1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MailjetProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", subject: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not to or not subject or not body:
            raise ProviderException("To, subject, and body are required")

        payload = {
            "Messages": [{
                "From": {"Email": self.authentication_config.from_email},
                "To": [{"Email": to}],
                "Subject": subject,
                "TextPart": body
            }]
        }

        try:
            response = requests.post(
                f"{self.MAILJET_API}/send",
                json=payload,
                auth=(self.authentication_config.api_key, self.authentication_config.secret_key),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Mailjet API error: {e}")

        self.logger.info("Email sent via Mailjet")
        return {"status": "success"}
