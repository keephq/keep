"""Sendgrid email provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SendgridProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Sendgrid API Key", "sensitive": True},
        default=""
    )
    from_email: str = dataclasses.field(
        metadata={"required": True, "description": "Sender email address"},
        default=""
    )

class SendgridProvider(BaseProvider):
    """Sendgrid email provider."""
    
    PROVIDER_DISPLAY_NAME = "Sendgrid"
    PROVIDER_CATEGORY = ["Collaboration"]
    SENDGRID_API = "https://api.sendgrid.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SendgridProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", subject: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not subject or not message:
            raise ProviderException("to, subject, and message are required")

        data = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self.authentication_config.from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": message}]
        }

        try:
            response = requests.post(
                f"{self.SENDGRID_API}/v3/mail/send",
                json=data,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sendgrid API error: {e}")

        self.logger.info("Email sent via Sendgrid")
        return {"status": "success"}
