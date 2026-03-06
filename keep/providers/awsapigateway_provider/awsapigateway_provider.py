"""AWS API Gateway provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import boto3

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AWSAPIGatewayProviderAuthConfig:
    access_key_id: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Access Key ID"},
        default=""
    )
    secret_access_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Secret Access Key", "sensitive": True},
        default=""
    )
    region: str = dataclasses.field(
        metadata={"required": True, "description": "AWS Region"},
        default="us-east-1"
    )

class AWSAPIGatewayProvider(BaseProvider):
    """AWS API Gateway provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS API Gateway"
    PROVIDER_CATEGORY = ["API Gateway"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AWSAPIGatewayProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, api_id: str = "", stage_name: str = "", **kwargs: Dict[str, Any]):
        if not api_id or not stage_name:
            raise ProviderException("API ID and stage name are required")

        try:
            client = boto3.client(
                "apigateway",
                aws_access_key_id=self.authentication_config.access_key_id,
                aws_secret_access_key=self.authentication_config.secret_access_key,
                region_name=self.authentication_config.region
            )
            
            response = client.create_deployment(
                restApiId=api_id,
                stageName=stage_name
            )
        except Exception as e:
            raise ProviderException(f"AWS API Gateway error: {e}")

        self.logger.info(f"AWS API Gateway deployed: {api_id}/{stage_name}")
        return {"status": "success", "api_id": api_id}
