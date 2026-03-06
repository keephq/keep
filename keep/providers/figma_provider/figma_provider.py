"""Figma design collaboration provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FigmaProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Figma Access Token", "sensitive": True},
        default=""
    )

class FigmaProvider(BaseProvider):
    """Figma design collaboration provider."""
    
    PROVIDER_DISPLAY_NAME = "Figma"
    PROVIDER_CATEGORY = ["Design & Creative"]
    FIGMA_API = "https://api.figma.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FigmaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, file_key: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not file_key or not message:
            raise ProviderException("File key and message are required")

        payload = {
            "message": message
        }

        try:
            response = requests.post(
                f"{self.FIGMA_API}/files/{file_key}/comments",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Figma API error: {e}")

        self.logger.info(f"Figma comment added to file: {file_key}")
        return {"status": "success", "file_key": file_key}
