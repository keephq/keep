"""BigPanda incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BigPandaProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "BigPanda API Key", "sensitive": True},
        default=""
    )
    app_key: str = dataclasses.field(
        metadata={"required": True, "description": "BigPanda App Key"},
        default=""
    )

class BigPandaProvider(BaseProvider):
    """BigPanda incident provider."""
    
    PROVIDER_DISPLAY_NAME = "BigPanda"
    PROVIDER_CATEGORY = ["Incident Management"]
    BIGPANDA_API = "https://api.bigpanda.io"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BigPandaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, status: str = "critical", message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "app_key": self.authentication_config.app_key,
            "status": status,
            "message": message
        }

        try:
            response = requests.post(
                f"{self.BIGPANDA_API}/data/v2/alerts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"BigPanda API error: {e}")

        self.logger.info("BigPanda incident created")
        return {"status": "success"}
