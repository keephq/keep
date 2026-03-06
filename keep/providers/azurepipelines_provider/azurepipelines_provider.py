"""Azure Pipelines CI/CD provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AzurePipelinesProviderAuthConfig:
    personal_access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Azure DevOps PAT", "sensitive": True},
        default=""
    )
    organization: str = dataclasses.field(
        metadata={"required": True, "description": "Azure DevOps Organization"},
        default=""
    )
    project: str = dataclasses.field(
        metadata={"required": True, "description": "Azure DevOps Project"},
        default=""
    )

class AzurePipelinesProvider(BaseProvider):
    """Azure Pipelines CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "Azure Pipelines"
    PROVIDER_CATEGORY = ["CI/CD"]
    AZURE_API = "https://dev.azure.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AzurePipelinesProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, definition_id: str = "", **kwargs: Dict[str, Any]):
        if not definition_id:
            raise ProviderException("Definition ID is required")

        import base64
        auth_str = f":{self.authentication_config.personal_access_token}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()

        payload = {
            "definition": {"id": int(definition_id)},
            "sourceBranch": kwargs.get("sourceBranch", "refs/heads/main"),
            "parameters": kwargs.get("parameters", "{}")
        }

        try:
            response = requests.post(
                f"{self.AZURE_API}/{self.authentication_config.organization}/{self.authentication_config.project}/_apis/build/builds?api-version=6.0",
                json=payload,
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Azure Pipelines API error: {e}")

        self.logger.info(f"Azure Pipeline triggered: {definition_id}")
        return {"status": "success", "definition_id": definition_id}
