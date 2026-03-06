"""Google Cloud Functions provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GCPFunctionsProviderAuthConfig:
    function_url: str = dataclasses.field(
        metadata={"required": True, "description": "Cloud Function URL"},
        default=""
    )
    auth_token: str = dataclasses.field(
        metadata={"description": "Authorization Token", "sensitive": True},
        default=""
    )

class GCPFunctionsProvider(BaseProvider):
    """Google Cloud Functions provider."""
    
    PROVIDER_DISPLAY_NAME = "Google Cloud Functions"
    PROVIDER_CATEGORY = ["Cloud"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GCPFunctionsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, payload: Dict = None, **kwargs: Dict[str, Any]):
        if not payload:
            payload = {}

        headers = {"Content-Type": "application/json"}
        if self.authentication_config.auth_token:
            headers["Authorization"] = f"Bearer {self.authentication_config.auth_token}"

        try:
            response = requests.post(
                self.authentication_config.function_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GCP Functions API error: {e}")

        self.logger.info("Google Cloud Function invoked")
        return {"status": "success"}
