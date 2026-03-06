"""Zendesk ticketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ZendeskProviderAuthConfig:
    subdomain: str = dataclasses.field(
        metadata={"required": True, "description": "Zendesk Subdomain"},
        default=""
    )
    email: str = dataclasses.field(
        metadata={"required": True, "description": "Email"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "API Token", "sensitive": True},
        default=""
    )

class ZendeskProvider(BaseProvider):
    """Zendesk ticketing provider."""
    
    PROVIDER_DISPLAY_NAME = "Zendesk"
    PROVIDER_CATEGORY = ["ITSM"]
    ZENDESK_API = "https://{subdomain}.zendesk.com/api/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZendeskProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, subject: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not subject or not body:
            raise ProviderException("Subject and body are required")

        payload = {
            "ticket": {
                "subject": subject,
                "comment": {"body": body}
            }
        }

        try:
            response = requests.post(
                self.ZENDESK_API.format(subdomain=self.authentication_config.subdomain) + "/tickets",
                json=payload,
                auth=(f"{self.authentication_config.email}/token", self.authentication_config.api_token),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Zendesk API error: {e}")

        self.logger.info("Zendesk ticket created")
        return {"status": "success"}
