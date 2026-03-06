"""HubSpot CRM and marketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HubSpotProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "HubSpot Access Token", "sensitive": True},
        default=""
    )

class HubSpotProvider(BaseProvider):
    """HubSpot CRM and marketing provider."""
    
    PROVIDER_DISPLAY_NAME = "HubSpot"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    HUBSPOT_API = "https://api.hubapi.com"
    
    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HubSpotProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, contact_email: str = "", subject: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not contact_email or not message:
            raise ProviderException("Contact email and message are required")
        
        payload = {
            "properties": {
                "email": contact_email,
                "subject": subject,
                "message": message
            }
        }

        try:
            response = requests.post(
                f"{self.HUBSPOT_API}/crm/v3/objects/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"HubSpot API error: {e}")

        self.logger.info(f"HubSpot email sent to: {contact_email}")
        return {"status": "success", "contact_email": contact_email}
