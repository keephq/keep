"""Monday.com work management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MondayProviderAuthConfig:
    api_key: str = dataclasses.field(
    metadata={"required": True, "description": "Monday.com API Key", "sensitive": True},
    default=""
)

class MondayProvider(BaseProvider):
    """Monday.com work management provider."""
    
    PROVIDER_DISPLAY_NAME = "Monday.com"
    PROVIDER_CATEGORY = ["Productivity"]
    MONDAY_API = "https://api.monday.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
    super().__init__(context_manager, provider_id, config)

    def validate_config(self):
    self.authentication_config = MondayProviderAuthConfig(**self.config.authentication)

    def dispose(self):
    pass

    def _notify(self, board_id: str = "", item_name: str = "", **kwargs: Dict[str, Any]):
    if not board_id or not item_name:
    raise ProviderException("Board ID and item name are required")

    query = """
    mutation ($boardId: ID!, $itemName: String!) {
    create_item(board_id: $boardId, item_name: $itemName) {
    id
    }
    }
    """

    variables = {
    "boardId": board_id,
    "itemName": item_name
    }

    try:
    response = requests.post(
    self.MONDAY_API,
    json={"query": query, "variables": variables},
    headers={
    "Authorization": self.authentication_config.api_key,
    "Content-Type": "application/json"
    },
    timeout=30
    )
    response.raise_for_status()
    except requests.exceptions.RequestException as e:
    raise ProviderException(f"Monday.com API error: {e}")

    self.logger.info(f"Monday.com item created: {item_name}")
    return {"status": "success", "item_name": item_name}
