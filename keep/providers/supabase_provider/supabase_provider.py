"""Supabase backend platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SupabaseProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Supabase API Key", "sensitive": True},
        default=""
    )
    project_url: str = dataclasses.field(
        metadata={"required": True, "description": "Supabase Project URL"},
        default=""
    )

class SupabaseProvider(BaseProvider):
    """Supabase backend platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Supabase"
    PROVIDER_CATEGORY = ["Backend"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SupabaseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, table: str = "", data: dict = None, **kwargs: Dict[str, Any]):
        if not table or not data:
            raise ProviderException("Table and data are required")

        try:
            response = requests.post(
                f"{self.authentication_config.project_url}/rest/v1/{table}",
                json=data,
                headers={
                    "apikey": self.authentication_config.api_key,
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Supabase API error: {e}")

        self.logger.info(f"Supabase record created: {table}")
        return {"status": "success", "table": table}
