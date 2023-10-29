import json
import logging
import os

import pydantic
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerservice import ContainerServiceClient

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory

@pydantic.dataclasses.dataclass
class AzureProviderAuthConfig:
    """Azure AKS authentication configuration."""

    resource_group: str = pydantic.Field(
        metadata={"required": True, "description": "Azure Resource Group name"}
    )
    cluster_name: str = pydantic.Field(
        metadata={"required": True, "description": "Azure AKS cluster name"}
    )

class AzureProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._resource_group = self.authentication_config.resource_group
        self._cluster_name = self.authentication_config.cluster_name
        self._kubeconfig_path = "/path/to/azure/kubeconfig.yaml"

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = AzureProviderAuthConfig(**self.config.authentication)

    @property
    def client(self):
        config.load_kube_config(config_file=self._kubeconfig_path)
        return client.CoreV1Api()

    def _query(self, command_type: str, **kwargs: dict):
        if command_type == "get_pods":
            try:
                pods = self.client.list_pod_for_all_namespaces(watch=False)
                return [pod.to_dict() for pod in pods.items]
            except ApiException as e:
                raise Exception(f"Error querying AKS for pods: {str(e)}")
        raise NotImplementedError("Command type not implemented")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Set the AZURE_AUTH_LOCATION environment variable to the path of your Azure authentication file.
    azure_auth_location = os.environ.get("AZURE_AUTH_LOCATION")

    resource_group = "your-aks-resource-group"
    cluster_name = "your-aks-cluster"

    config = {
        "authentication": {
            "resource_group": resource_group,
            "cluster_name": cluster_name,
        }
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="aks-demo",
        provider_type="aks",
        provider_config=config,
    )
    # Query AKS resources using the provider's methods.
    pods = provider.query(command_type="get_pods")
    print(pods)
