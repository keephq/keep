"""Resend email provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ResendProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Resend API Key", "sensitive": True},
        default=""
    )

class ResendProvider(BaseProvider):
    """Resend email provider."""
    
    PROVIDER_DISPLAY_NAME = "Resend"
    PROVIDER_CATEGORY = ["Collaboration"]
    RESEND_API = "https://api.resend.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ResendProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", subject: str = "", message: str = "", from_email: str = "onboarding@resend.dev", **kwargs: Dict[str, Any]):
        if not to or not subject or not message:
            raise ProviderException("To, subject, and message are required")

        data = {
            "from": from_email,
            "to": [to],
            "subject": subject,
            "text": message
        }

        try:
            response = requests.post(
                f"{self.RESEND_API}/emails",
                json=data,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Resend API error: {e}")

        self.logger.info("Email sent via Resend")
        return {"status": "success"}
