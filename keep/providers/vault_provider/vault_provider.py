"""HashiCorp Vault secrets provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VaultProviderAuthConfig:
    url: str = dataclasses.field(
        metadata={"required": True, "description": "Vault URL"},
        default=""
    )
    token: str = dataclasses.field(
        metadata={"required": True, "description": "Vault Token", "sensitive": True},
        default=""
    )

class VaultProvider(BaseModel):
    """HashiCorp Vault secrets provider."""
    
    PROVIDER_DISPLAY_NAME = "HashiCorp Vault"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VaultProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, path: str = "", data: Dict = None, **kwargs: Dict[str, Any]):
        if not path or not data:
            raise ProviderException("Path and data are required")

        try:
            response = requests.post(
                f"{self.authentication_config.url}/v1/{path}",
                json=data,
                headers={"X-Vault-Token": self.authentication_config.token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Vault API error: {e}")

        self.logger.info("Vault secret written")
        return {"status": "success"}
