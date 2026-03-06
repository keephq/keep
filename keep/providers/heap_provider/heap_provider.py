"""Heap Analytics provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HeapProviderAuthConfig:
    app_id: str = dataclasses.field(
        metadata={"required": True, "description": "Heap App ID"},
        default=""
    )

class HeapProvider(BaseProvider):
    """Heap Analytics provider."""
    
    PROVIDER_DISPLAY_NAME = "Heap"
    PROVIDER_CATEGORY = ["Analytics"]
    HEAP_API = "https://heapanalytics.com/api"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HeapProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, identity: str = "", event: str = "", properties: Dict = None, **kwargs: Dict[str, Any]):
        if not identity or not event:
            raise ProviderException("Identity and event are required")

        payload = {
            "app_id": self.authentication_config.app_id,
            "identity": identity,
            "event": event,
            "properties": properties or {}
        }

        try:
            response = requests.post(
                f"{self.HEAP_API}/track",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Heap API error: {e}")

        self.logger.info("Heap event tracked")
        return {"status": "success"}
