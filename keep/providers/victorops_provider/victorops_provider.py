"""VictorOps (Splunk On-Call) provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VictorOpsProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "VictorOps API Key", "sensitive": True},
        default=""
    )
    routing_key: str = dataclasses.field(
        metadata={"required": True, "description": "Routing Key"},
        default=""
    )

class VictorOpsProvider(BaseProvider):
    """VictorOps (Splunk On-Call) provider."""
    
    PROVIDER_DISPLAY_NAME = "VictorOps"
    PROVIDER_CATEGORY = ["Incident Management"]
    VICTOROPS_API = "https://api.victorops.com/api-public"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VictorOpsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", entity_id: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        url = f"{self.VICTOROPS_API}/{self.authentication_config.routing_key}"

        payload = {
            "message_type": "CRITICAL",
            "entity_id": entity_id or message[:50],
            "state_message": message
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"X-VO-Api-Id": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"VictorOps API error: {e}")

        self.logger.info("VictorOps incident created")
        return {"status": "success"}
