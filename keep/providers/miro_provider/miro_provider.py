"""Miro collaborative whiteboard provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MiroProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Miro Access Token", "sensitive": True},
        default=""
    )

class MiroProvider(BaseProvider):
    """Miro collaborative whiteboard provider."""
    
    PROVIDER_DISPLAY_NAME = "Miro"
    PROVIDER_CATEGORY = ["Collaboration"]
    MIRO_API = "https://api.miro.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MiroProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, board_id: str = "", text: str = "", x: int = 0, y: int = 0, **kwargs: Dict[str, Any]):
        if not board_id or not text:
            raise ProviderException("Board ID and text are required")

        payload = {
            "data": {"content": text},
            "position": {"x": x, "y": y}
        }

        try:
            response = requests.post(
                f"{self.MIRO_API}/boards/{board_id}/sticky_notes",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Miro API error: {e}")

        self.logger.info("Miro sticky note created")
        return {"status": "success"}
