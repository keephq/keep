"""Kubernetes provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class KubernetesProviderAuthConfig:
    api_server: str = dataclasses.field(
        metadata={"required": True, "description": "Kubernetes API Server URL"},
        default=""
    )
    token: str = dataclasses.field(
        metadata={"required": True, "description": "Bearer Token", "sensitive": True},
        default=""
    )
    namespace: str = dataclasses.field(
        metadata={"required": True, "description": "Namespace"},
        default="default"
    )

class KubernetesProvider(BaseProvider):
    """Kubernetes provider."""
    
    PROVIDER_DISPLAY_NAME = "Kubernetes"
    PROVIDER_CATEGORY = ["Cloud"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = KubernetesProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, pod_name: str = "", action: str = "restart", **kwargs: Dict[str, Any]):
        if not pod_name:
            raise ProviderException("Pod name is required")

        try:
            if action == "restart":
                response = requests.delete(
                    f"{self.authentication_config.api_server}/api/v1/namespaces/{self.authentication_config.namespace}/pods/{pod_name}",
                    headers={"Authorization": f"Bearer {self.authentication_config.token}"},
                    timeout=30
                )
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Kubernetes API error: {e}")

        self.logger.info(f"Kubernetes pod {action} initiated")
        return {"status": "success"}
