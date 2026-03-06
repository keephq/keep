"""AWS SNS SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SNSProviderAuthConfig:
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

class SNSProvider(BaseProvider):
    """AWS SNS SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS SNS"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms", "aws"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SNSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, phone_number: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not phone_number or not message:
            raise ProviderException("Phone number and message are required")

        # Note: In production, use boto3. This is a simplified version.
        import hashlib
        import hmac
        import time
        
        payload = {
            "Action": "Publish",
            "PhoneNumber": phone_number,
            "Message": message,
            "Version": "2010-03-31",
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        try:
            # Simplified - real implementation would use boto3
            response = requests.post(
                f"https://sns.{self.authentication_config.region}.amazonaws.com/",
                data=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"AWS SNS API error: {e}")

        self.logger.info("SMS sent via AWS SNS")
        return {"status": "success"}
