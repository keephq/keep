"""Marketo marketing automation provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MarketoProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Marketo Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Marketo Client Secret", "sensitive": True},
        default=""
    )
    munchkin_id: str = dataclasses.field(
        metadata={"required": True, "description": "Marketo Munchkin ID"},
        default=""
    )

class MarketoProvider(BaseProvider):
    """Marketo marketing automation provider."""
    
    PROVIDER_DISPLAY_NAME = "Marketo"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    
    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.munchkin_id = self.authentication_config.munchkin_id
        self.api_url = f"https://{self.munchkin_id}.mktorest.com/rest/v1"

    def validate_config(self):
        self.authentication_config = MarketoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, email: str = "", subject: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not email or not subject:
            raise ProviderException("Email and subject are required")

        try:
            # Get access token
            auth_response = requests.post(
                f"https://{self.munchkin_id}.mktorest.com/identity/oauth/token",
                params={
                    "grant_type": "client_credentials",
                    "client_id": self.authentication_config.client_id,
                    "client_secret": self.authentication_config.client_secret
                },
                timeout=30
            )
            auth_response.raise_for_status()
            access_token = auth_response.json().get("access_token")

            # Send email
            response = requests.post(
                f"{self.api_url}/emails.json",
                json={
                    "email": email,
                    "subject": subject,
                    "body": message
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Marketo API error: {e}")

        self.logger.info(f"Marketo email sent to: {email}")
        return {"status": "success", "email": email}
