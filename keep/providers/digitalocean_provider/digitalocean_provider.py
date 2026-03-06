"""DigitalOcean cloud provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DigitalOceanProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "DigitalOcean API Token", "sensitive": True},
        default=""
    )

class DigitalOceanProvider(BaseProvider):
    """DigitalOcean cloud provider."""
    
    PROVIDER_DISPLAY_NAME = "DigitalOcean"
    PROVIDER_CATEGORY = ["Network Infrastructure"]
    DIGITALOCEAN_API = "https://api.digitalocean.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DigitalOceanProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, droplet_name: str = "", region: str = "nyc1", size: str = "s-1vcpu-1gb", **kwargs: Dict[str, Any]):
        if not droplet_name:
            raise ProviderException("Droplet name is required")

        payload = {
            "name": droplet_name,
            "region": region,
            "size": size,
            "image": kwargs.get("image", "ubuntu-20-04-x64")
        }

        try:
            response = requests.post(
                f"{self.DIGITALOCEAN_API}/droplets",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"DigitalOcean API error: {e}")

        self.logger.info(f"DigitalOcean droplet created: {droplet_name}")
        return {"status": "success", "droplet_name": droplet_name}
