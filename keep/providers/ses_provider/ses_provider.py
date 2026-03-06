"""AWS SES Email provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SESProviderAuthConfig:
    access_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Access Key", "sensitive": True},
        default=""
    )
    secret_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Secret Key", "sensitive": True},
        default=""
    )
    region: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Region"},
        default="us-east-1"
    )
    from_email: str = dataclasses.field(
        metadata={"required": True, "description": "From Email Address"},
        default=""
    )

class SESProvider(BaseProvider):
    """AWS SES Email provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS SES"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["email", "aws"]
    SES_API = "https://email.{region}.amazonaws.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SESProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", subject: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not to or not subject or not body:
            raise ProviderException("To, subject, and body are required")

        # Note: In production, use boto3. This is a simplified version.
        payload = {
            "Action": "SendEmail",
            "Source": self.authentication_config.from_email,
            "Destination.ToAddresses.member.1": to,
            "Message.Subject.Data": subject,
            "Message.Body.Text.Data": body,
            "Version": "2010-12-01"
        }

        try:
            response = requests.post(
                self.SES_API.format(region=self.authentication_config.region),
                data=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"SES API error: {e}")

        self.logger.info("Email sent via AWS SES")
        return {"status": "success"}
