"""Mailchimp email marketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MailchimpProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Mailchimp API Key", "sensitive": True},
        default=""
    )
    server_prefix: str = dataclasses.field(
        metadata={"required": True, "description": "Mailchimp Server Prefix (e.g., us1)"},
        default="us1"
    )

class MailchimpProvider(BaseProvider):
    """Mailchimp email marketing provider."""
    
    PROVIDER_DISPLAY_NAME = "Mailchimp"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    
    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.server_prefix = self.authentication_config.server_prefix
        self.api_url = f"https://{self.server_prefix}.api.mailchimp.com/3.0"

    def validate_config(self):
        self.authentication_config = MailchimpProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, list_id: str = "", subject: str = "", 
                from_email: str = "", from_name: str = "", 
                html_content: str = "", text_content: str = "", **kwargs: Dict[str, Any]):
        if not list_id or not subject:
            raise ProviderException("List ID and subject are required")
        
        payload = {
            "type": "regular",
            "recipients": {"list_id": list_id, "list_is_active": True},
            "settings": {
                "subject_line": subject,
                "from_name": from_name,
                "reply_to": from_email
            }
        }
        
        if html_content:
            payload["content"]["html"] = html_content
        if text_content:
            payload["content"]["text"] = text_content

        try:
            response = requests.post(
                f"{self.api_url}/campaigns",
                json=payload,
                auth=("apikey", self.authentication_config.api_key),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Mailchimp API error: {e}")

        self.logger.info(f"Mailchimp campaign created: {list_id}")
        return {"status": "success", "list_id": list_id}
