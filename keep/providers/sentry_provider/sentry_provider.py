"""Sentry error tracking provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SentryProviderAuthConfig:
    auth_token: str = dataclasses.field(
        metadata={"required": True, "description": "Sentry Auth Token", "sensitive": True},
        default=""
    )

class SentryProvider(BaseProvider):
    """Sentry error tracking provider."""
    
    PROVIDER_DISPLAY_NAME = "Sentry"
    PROVIDER_CATEGORY = ["Monitoring"]
    SENTRY_API = "https://sentry.io/api/0"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SentryProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", level: str = "error", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "message": message,
            "level": level
        }

        try:
            response = requests.post(
                f"{self.SENTRY_API}/projects",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.auth_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sentry API error: {e}")

        self.logger.info("Sentry event created")
        return {"status": "success"}
