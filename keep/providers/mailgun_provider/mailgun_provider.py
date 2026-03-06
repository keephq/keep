"""Mailgun email provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MailgunProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Mailgun API Key", "sensitive": True},
        default=""
    )
    domain: str = dataclasses.field(
        metadata={"required": True, "description": "Mailgun Domain"},
        default=""
    )

class MailgunProvider(BaseProvider):
    """Mailgun email provider."""
    
    PROVIDER_DISPLAY_NAME = "Mailgun"
    PROVIDER_CATEGORY = ["Collaboration"]
    MAILGUN_API = "https://api.mailgun.net/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MailgunProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", subject: str = "", message: str = "", from_email: str = "", **kwargs: Dict[str, Any]):
        if not to or not subject or not message:
            raise ProviderException("To, subject, and message are required")

        data = {
            "from": from_email or f"noreply@{self.authentication_config.domain}",
            "to": [to],
            "subject": subject,
            "text": message
        }

        try:
            response = requests.post(
                f"{self.MAILGUN_API}/{self.authentication_config.domain}/messages",
                auth=("api", self.authentication_config.api_key),
                data=data,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Mailgun API error: {e}")

        self.logger.info("Email sent via Mailgun")
        return {"status": "success"}
