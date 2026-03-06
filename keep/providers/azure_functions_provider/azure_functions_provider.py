"""Azure Functions provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AzureFunctionsProviderAuthConfig:
    function_url: str = dataclasses.field(
        metadata={"required": True, "description": "Azure Function URL", "sensitive": True},
        default=""
    )
    function_key: str = dataclasses.field(
        metadata={"description": "Function Key", "sensitive": True},
        default=""
    )

class AzureFunctionsProvider(BaseProvider):
    """Azure Functions provider."""
    
    PROVIDER_DISPLAY_NAME = "Azure Functions"
    PROVIDER_CATEGORY = ["Cloud"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AzureFunctionsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, payload: Dict = None, **kwargs: Dict[str, Any]):
        if not payload:
            payload = {}

        headers = {}
        if self.authentication_config.function_key:
            headers["x-functions-key"] = self.authentication_config.function_key

        try:
            response = requests.post(
                self.authentication_config.function_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Azure Functions API error: {e}")

        self.logger.info("Azure Function invoked")
        return {"status": "success"}
