"""Basecamp project management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BasecampProviderAuthConfig:
    access_token: str = dataclasses.field(
    metadata={"required": True, "description": "Basecamp Access Token", "sensitive": True},
    default=""
)
    account_id: str = dataclasses.field(
    metadata={"required": True, "description": "Basecamp Account ID"},
    default=""
)

class BasecampProvider(BaseProvider):
    """Basecamp project management provider."""
    
    PROVIDER_DISPLAY_NAME = "Basecamp"
    PROVIDER_CATEGORY = ["Productivity"]
    BASECAMP_API = "https://3.basecampapi.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
    super().__init__(context_manager, provider_id, config)

    def validate_config(self):
    self.authentication_config = BasecampProviderAuthConfig(**self.config.authentication)

    def dispose(self):
    pass

    def _notify(self, project_id: str = "", subject: str = "", content: str = "", **kwargs: Dict[str, Any]):
    if not project_id or not subject:
    raise ProviderException("Project ID and subject are required")

    payload = {
    "subject": subject,
    "content": content,
    "status": "active"
    }

    try:
    response = requests.post(
    f"{self.BASECAMP_API}/{self.authentication_config.account_id}/buckets/{project_id}/messages.json",
    json=payload,
    headers={
    "Authorization": f"Bearer {self.authentication_config.access_token}",
    "Content-Type": "application/json"
    },
    timeout=30
    )
    response.raise_for_status()
    except requests.exceptions.RequestException as e:
    raise ProviderException(f"Basecamp API error: {e}")

    self.logger.info(f"Basecamp message created: {subject}")
    return {"status": "success", "subject": subject}
