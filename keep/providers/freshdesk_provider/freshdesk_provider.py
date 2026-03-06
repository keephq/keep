"""Freshdesk ticketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FreshdeskProviderAuthConfig:
    domain: str = dataclasses.field(
        metadata={"required": True, "description": "Freshdesk Domain"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "API Key", "sensitive": True},
        default=""
    )

class FreshdeskProvider(BaseProvider):
    """Freshdesk ticketing provider."""
    
    PROVIDER_DISPLAY_NAME = "Freshdesk"
    PROVIDER_CATEGORY = ["ITSM"]
    FRESHDESK_API = "https://{domain}.freshdesk.com/api/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FreshdeskProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, subject: str = "", description: str = "", email: str = "", priority: int = 1, **kwargs: Dict[str, Any]):
        if not subject or not description:
            raise ProviderException("Subject and description are required")

        payload = {
            "subject": subject,
            "description": description,
            "email": email,
            "priority": priority
        }

        try:
            response = requests.post(
                self.FRESHDESK_API.format(domain=self.authentication_config.domain) + "/tickets",
                json=payload,
                auth=(self.authentication_config.api_key, "X"),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Freshdesk API error: {e}")

        self.logger.info("Freshdesk ticket created")
        return {"status": "success"}
