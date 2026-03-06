"""Datadog monitoring provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DatadogProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Datadog API Key", "sensitive": True},
        default=""
    )
    app_key: str = dataclasses.field(
        metadata={"required": True, "description": "Datadog App Key", "sensitive": True},
        default=""
    )

class DatadogProvider(BaseProvider):
    """Datadog monitoring provider."""
    
    PROVIDER_DISPLAY_NAME = "Datadog"
    PROVIDER_CATEGORY = ["Monitoring"]
    DATADOG_API = "https://api.datadoghq.com/api/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DatadogProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", text: str = "", priority: str = "normal", **kwargs: Dict[str, Any]):
        if not title or not text:
            raise ProviderException("Title and text are required")

        payload = {
            "title": title,
            "text": text,
            "priority": priority
        }

        try:
            response = requests.post(
                f"{self.DATADOG_API}/events",
                json=payload,
                headers={
                    "DD-API-KEY": self.authentication_config.api_key,
                    "DD-APPLICATION-KEY": self.authentication_config.app_key
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Datadog API error: {e}")

        self.logger.info("Datadog event created")
        return {"status": "success"}
