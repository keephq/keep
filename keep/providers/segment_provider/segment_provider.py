"""Segment Analytics provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SegmentProviderAuthConfig:
    write_key: str = dataclasses.field(
        metadata={"required": True, "description": "Segment Write Key", "sensitive": True},
        default=""
    )

class SegmentProvider(BaseProvider):
    """Segment Analytics provider."""
    
    PROVIDER_DISPLAY_NAME = "Segment"
    PROVIDER_CATEGORY = ["Analytics"]
    SEGMENT_API = "https://api.segment.io/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SegmentProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, event: str = "", user_id: str = "", properties: Dict = None, **kwargs: Dict[str, Any]):
        if not event or not user_id:
            raise ProviderException("Event and user_id are required")

        payload = {
            "event": event,
            "userId": user_id,
            "properties": properties or {}
        }

        try:
            import base64
            auth = base64.b64encode(f"{self.authentication_config.write_key}:".encode()).decode()
            response = requests.post(
                f"{self.SEGMENT_API}/track",
                json=payload,
                headers={"Authorization": f"Basic {auth}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Segment API error: {e}")

        self.logger.info("Segment event tracked")
        return {"status": "success"}
