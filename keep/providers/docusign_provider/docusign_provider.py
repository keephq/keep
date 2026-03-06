"""DocuSign e-signature provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DocuSignProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "DocuSign Access Token", "sensitive": True},
        default=""
    )
    account_id: str = dataclasses.field(
        metadata={"required": True, "description": "DocuSign Account ID"},
        default=""
    )

class DocuSignProvider(BaseProvider):
    """DocuSign e-signature provider."""
    
    PROVIDER_DISPLAY_NAME = "DocuSign"
    PROVIDER_CATEGORY = ["Legal & Compliance"]
    DOCUSIGN_API = "https://demo.docusign.net/restapi/v2.1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DocuSignProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, envelope_id: str = "", status: str = "", **kwargs: Dict[str, Any]):
        if not envelope_id:
            raise ProviderException("Envelope ID is required")

        try:
            response = requests.get(
                f"{self.DOCUSIGN_API}/accounts/{self.authentication_config.account_id}/envelopes/{envelope_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"DocuSign API error: {e}")

        self.logger.info(f"DocuSign envelope status retrieved: {envelope_id}")
        return {"status": "success", "envelope_id": envelope_id}
