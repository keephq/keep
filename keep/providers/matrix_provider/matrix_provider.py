"""Matrix (Element) provider for decentralized messaging."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MatrixProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Matrix Access Token", "sensitive": True},
        default=""
    )
    homeserver: str = dataclasses.field(
        metadata={"required": True, "description": "Matrix Homeserver URL"},
        default=""
    )
    room_id: str = dataclasses.field(
        metadata={"required": True, "description": "Matrix Room ID"},
        default=""
    )

class MatrixProvider(BaseProvider):
    """Matrix (Element) messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Matrix"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MatrixProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        import uuid
        txn_id = str(uuid.uuid4())

        payload = {
            "msgtype": "m.text",
            "body": message
        }

        try:
            response = requests.put(
                f"{self.authentication_config.homeserver}/_matrix/client/v3/rooms/{self.authentication_config.room_id}/send/m.room.message/{txn_id}",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Matrix API error: {e}")

        self.logger.info("Matrix message sent")
        return {"status": "success"}
