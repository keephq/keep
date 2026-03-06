"""VictorOps incident provider via REST API."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VictorOps2ProviderAuthConfig:
    api_id: str = dataclasses.field(
        metadata={"required": True, "description": "VictorOps API ID"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "VictorOps API Key", "sensitive": True},
        default=""
    )

class VictorOps2Provider(BaseProvider):
    """VictorOps incident provider via REST API."""
    
    PROVIDER_DISPLAY_NAME = "VictorOps REST"
    PROVIDER_CATEGORY = ["Incident Management"]
    VICTOROPS_API = "https://api.victorops.com/api-public/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VictorOps2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "message": message,
            "entity_id": message[:50]
        }

        try:
            response = requests.post(
                f"{self.VICTOROPS_API}/incidents",
                json=payload,
                headers={
                    "X-VO-Api-Id": self.authentication_config.api_id,
                    "X-VO-Api-Key": self.authentication_config.api_key
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"VictorOps API error: {e}")

        self.logger.info("VictorOps incident created")
        return {"status": "success"}
