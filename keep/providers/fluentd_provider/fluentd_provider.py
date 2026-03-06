"""Fluentd logging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FluentdProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Fluentd Host"},
        default=""
    )
    port: int = dataclasses.field(
        metadata={"required": True, "description": "Fluentd Port"},
        default=9880
    )
    tag: str = dataclasses.field(
        metadata={"required": True, "description": "Fluentd Tag"},
        default="keep"
    )

class FluentdProvider(BaseProvider):
    """Fluentd logging provider."""
    
    PROVIDER_DISPLAY_NAME = "Fluentd"
    PROVIDER_CATEGORY = ["Logging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FluentdProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {"message": message}

        try:
            response = requests.post(
                f"http://{self.authentication_config.host}:{self.authentication_config.port}/{self.authentication_config.tag}",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Fluentd API error: {e}")

        self.logger.info("Fluentd event sent")
        return {"status": "success"}
