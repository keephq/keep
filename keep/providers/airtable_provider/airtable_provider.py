"""Airtable database provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AirtableProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Airtable API Key", "sensitive": True},
        default=""
    )
    base_id: str = dataclasses.field(
        metadata={"required": True, "description": "Airtable Base ID"},
        default=""
    )

class AirtableProvider(BaseProvider):
    """Airtable database provider."""
    
    PROVIDER_DISPLAY_NAME = "Airtable"
    PROVIDER_CATEGORY = ["Database"]
    AIRTABLE_API = "https://api.airtable.com/v0"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AirtableProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, table_name: str = "", fields: dict = None, **kwargs: Dict[str, Any]):
        if not table_name or not fields:
            raise ProviderException("Table name and fields are required")

        payload = {
            "records": [{
                "fields": fields
            }]
        }

        try:
            response = requests.post(
                f"{self.AIRTABLE_API}/{self.authentication_config.base_id}/{table_name}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Airtable API error: {e}")

        self.logger.info(f"Airtable record created: {table_name}")
        return {"status": "success", "table_name": table_name}
