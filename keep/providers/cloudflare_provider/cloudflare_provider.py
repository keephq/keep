"""Cloudflare network infrastructure provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CloudflareProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Cloudflare API Token", "sensitive": True},
        default=""
    )
    zone_id: str = dataclasses.field(
        metadata={"required": True, "description": "Cloudflare Zone ID"},
        default=""
    )

class CloudflareProvider(BaseProvider):
    """Cloudflare network infrastructure provider."""
    
    PROVIDER_DISPLAY_NAME = "Cloudflare"
    PROVIDER_CATEGORY = ["Network Infrastructure"]
    CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CloudflareProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, record_name: str = "", record_type: str = "A", content: str = "", **kwargs: Dict[str, Any]):
        if not record_name or not content:
            raise ProviderException("Record name and content are required")

        payload = {
            "type": record_type,
            "name": record_name,
            "content": content,
            "ttl": kwargs.get("ttl", 1),
            "proxied": kwargs.get("proxied", False)
        }

        try:
            response = requests.post(
                f"{self.CLOUDFLARE_API}/zones/{self.authentication_config.zone_id}/dns_records",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Cloudflare API error: {e}")

        self.logger.info(f"Cloudflare DNS record created: {record_name}")
        return {"status": "success", "record_name": record_name}
