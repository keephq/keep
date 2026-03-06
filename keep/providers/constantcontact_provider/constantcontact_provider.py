"""Constant Contact email marketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ConstantContactProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Constant Contact Access Token", "sensitive": True},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Constant Contact API Key"},
        default=""
    )

class ConstantContactProvider(BaseProvider):
    """Constant Contact email marketing provider."""
    
    PROVIDER_DISPLAY_NAME = "Constant Contact"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    CONSTANTCONTACT_API = "https://api.cc.email/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ConstantContactProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, campaign_name: str = "", subject: str = "", 
                html_content: str = "", email_list_ids: List[str] = None, **kwargs: Dict[str, Any]):
        if not campaign_name or not subject:
            raise ProviderException("Campaign name and subject are required")

        payload = {
            "name": campaign_name,
            "subject": subject,
            "content": [{"html": html_content}] if html_content else [],
            "email_campaign_lists": [{"list_id": lid} for lid in (email_list_ids or [])]
        }

        try:
            response = requests.post(
                f"{self.CONSTANTCONTACT_API}/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "x-api-key": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Constant Contact API error: {e}")

        self.logger.info(f"Constant Contact campaign created: {campaign_name}")
        return {"status": "success", "campaign_name": campaign_name}
