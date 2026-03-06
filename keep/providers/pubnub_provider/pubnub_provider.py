"""PubNub realtime messaging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PubNubProviderAuthConfig:
    publish_key: str = dataclasses.field(
        metadata={"required": True, "description": "PubNub Publish Key", "sensitive": True},
        default=""
    )
    subscribe_key: str = dataclasses.field(
        metadata={"required": True, "description": "PubNub Subscribe Key", "sensitive": True},
        default=""
    )
    channel: str = dataclasses.field(
        metadata={"required": True, "description": "PubNub Channel Name"},
        default=""
    )

class PubNubProvider(BaseProvider):
    """PubNub realtime messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "PubNub"
    PROVIDER_CATEGORY = ["Messaging"]
    PROVIDER_TAGS = ["realtime"]
    PUBNUB_API = "https://ps.pndsn.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PubNubProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {"message": message}

        try:
            response = requests.post(
                f"{self.PUBNUB_API}/publish/{self.authentication_config.publish_key}/{self.authentication_config.subscribe_key}/0/{self.authentication_config.channel}",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"PubNub API error: {e}")

        self.logger.info("PubNub message published")
        return {"status": "success"}
