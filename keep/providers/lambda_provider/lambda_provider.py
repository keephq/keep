"""AWS Lambda provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LambdaProviderAuthConfig:
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
    function_name: str = dataclasses.field(
        metadata={"required": True, "description": "Lambda Function Name"},
        default=""
    )

class LambdaProvider(BaseProvider):
    """AWS Lambda provider."""
    
    PROVIDER_DISPLAY_NAME = "AWS Lambda"
    PROVIDER_CATEGORY = ["Cloud"]
    LAMBDA_API = "https://lambda.{region}.amazonaws.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LambdaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, payload: Dict = None, **kwargs: Dict[str, Any]):
        if not payload:
            payload = {}

        # Note: In production, use boto3. Simplified version.
        try:
            response = requests.post(
                f"{self.LAMBDA_API.format(region=self.authentication_config.region)}/2015-03-31/functions/{self.authentication_config.function_name}/invocations",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Lambda API error: {e}")

        self.logger.info("Lambda function invoked")
        return {"status": "success", "result": response.text[:100]}
