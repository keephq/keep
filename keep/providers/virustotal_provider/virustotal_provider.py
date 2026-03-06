"""VirusTotal malware analysis provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VirusTotalProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "VirusTotal API Key", "sensitive": True},
        default=""
    )

class VirusTotalProvider(BaseProvider):
    """VirusTotal malware analysis provider."""
    
    PROVIDER_DISPLAY_NAME = "VirusTotal"
    PROVIDER_CATEGORY = ["Security"]
    VT_API = "https://www.virustotal.com/api/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VirusTotalProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, file_hash: str = "", **kwargs: Dict[str, Any]):
        if not file_hash:
            raise ProviderException("File hash is required")

        try:
            response = requests.get(
                f"{self.VT_API}/files/{file_hash}",
                headers={"x-apikey": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"VirusTotal API error: {e}")

        self.logger.info(f"VirusTotal analysis retrieved: {file_hash}")
        return {"status": "success", "file_hash": file_hash}
