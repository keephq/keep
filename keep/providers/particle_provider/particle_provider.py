"""Particle IoT provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ParticleProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Particle Access Token", "sensitive": True},
        default=""
    )
    device_id: str = dataclasses.field(
        metadata={"required": True, "description": "Device ID"},
        default=""
    )

class ParticleProvider(BaseModel):
    """Particle IoT provider."""
    
    PROVIDER_DISPLAY_NAME = "Particle"
    PROVIDER_CATEGORY = ["IoT"]
    PARTICLE_API = "https://api.particle.io/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ParticleProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, function_name: str = "", argument: str = "", **kwargs: Dict[str, Any]):
        if not function_name:
            raise ProviderException("Function name is required")

        try:
            response = requests.post(
                f"{self.PARTICLE_API}/devices/{self.authentication_config.device_id}/{function_name}",
                data={"arg": argument},
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Particle API error: {e}")

        self.logger.info("Particle function called")
        return {"status": "success"}
