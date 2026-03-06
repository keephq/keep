"""Linode cloud provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LinodeProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Linode API Token", "sensitive": True},
        default=""
    )

class LinodeProvider(BaseProvider):
    """Linode cloud provider."""
    
    PROVIDER_DISPLAY_NAME = "Linode"
    PROVIDER_CATEGORY = ["Network Infrastructure"]
    LINODE_API = "https://api.linode.com/v4"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LinodeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, label: str = "", region: str = "us-east", type: str = "g6-nanode-1", **kwargs: Dict[str, Any]):
        if not label:
            raise ProviderException("Label is required")

        payload = {
            "label": label,
            "region": region,
            "type": type,
            "image": kwargs.get("image", "linode/ubuntu20.04")
        }

        try:
            response = requests.post(
                f"{self.LINODE_API}/linode/instances",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Linode API error: {e}")

        self.logger.info(f"Linode instance created: {label}")
        return {"status": "success", "label": label}
