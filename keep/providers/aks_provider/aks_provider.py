import dataclasses
import logging

import pydantic
from azure.identity import ClientSecretCredential
from azure.mgmt.containerservice import ContainerServiceClient
from kubernetes import client, config

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.functions import cyaml
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class AksProviderAuthConfig:
    """AKS authentication configuration."""

    subscription_id: str = dataclasses.field(
        metadata={
            "name": "subscription_id",
            "description": "The azure subscription id",
            "required": True,
            "sensitive": True,
        }
    )
    client_id: str = dataclasses.field(
        metadata={
            "name": "client_id",
            "description": "The azure client id",
            "required": True,
            "sensitive": True,
        }
    )
    client_secret: str = dataclasses.field(
        metadata={
            "name": "client_secret",
            "description": "The azure client secret",
            "required": True,
            "sensitive": True,
        }
    )
    tenant_id: str = dataclasses.field(
        metadata={
            "name": "tenant_id",
            "description": "The azure tenant id",
            "required": True,
            "sensitive": True,
        }
    )
    resource_group_name: str = dataclasses.field(
        metadata={
            "name": "resource_group_name",
            "description": "The azure aks resource group name",
            "required": True,
            "sensitive": True,
        }
    )
    resource_name: str = dataclasses.field(
        metadata={
            "name": "resource_name",
            "description": "The azure aks cluster name",
            "required": True,
            "sensitive": True,
        }
    )


class AksProvider(BaseProvider):
    """Enrich alerts using data from AKS."""

    PROVIDER_DISPLAY_NAME = "Azure AKS"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._client = None

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = AksProviderAuthConfig(**self.config.authentication)

    @property
    def client(self):
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def __generate_client(self):
        try:
            # generate credential instance
            credential = ClientSecretCredential(
                tenant_id=self.authentication_config.tenant_id,
                client_id=self.authentication_config.client_id,
                client_secret=self.authentication_config.client_secret,
            )

            # generate aks client
            aks_client = ContainerServiceClient(
                credential=credential,
                subscription_id=self.authentication_config.subscription_id,
            )

            # get user credential for given cluster name
            cluster_creds = aks_client.managed_clusters.list_cluster_user_credentials(
                resource_group_name=self.authentication_config.resource_group_name,
                resource_name=self.authentication_config.resource_name,
            )

            # parse the kubeconfig (parsed as yml string)
            kubeconfig = cyaml.safe_load(
                cluster_creds.kubeconfigs[0].value.decode("utf-8")
            )

            config.load_kube_config_from_dict(config_dict=kubeconfig)

            self.logger.info("Loading kubeconfig...")

            return client.CoreV1Api()
        except Exception as e:
            raise ProviderException(f"Failed to load kubeconfig: {e}")

    def _query(self, command_type: str, **kwargs: dict):
        if command_type == "get_pods":
            pods = self.client.list_pod_for_all_namespaces(watch=False)
            return [pod.to_dict() for pod in pods.items]

        elif command_type == "get_pvc":
            pvcs = self.client.list_persistent_volume_claim_for_all_namespaces(
                watch=False
            )
            return [pvc.to_dict() for pvc in pvcs.items]

        elif command_type == "get_node_pressure":
            nodes = self.client.list_node(watch=False)
            node_pressures = []
            for node in nodes.items:
                pressures = {
                    "name": node.metadata.name,
                    "conditions": [],
                }
                for condition in node.status.conditions:
                    if condition.type in [
                        "MemoryPressure",
                        "DiskPressure",
                        "PIDPressure",
                    ]:
                        pressures["conditions"].append(condition.to_dict())
                node_pressures.append(pressures)
            return node_pressures

        raise NotImplementedError("command type not implemented")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Load environment variables
    import os

    config = {
        "authentication": {
            "subscription_id": os.environ.get("AKS_SUBSCRIPTION_ID"),
            "client_secret": os.environ.get("AKS_CLIENT_SECRET"),
            "client_id": os.environ.get("AKS_CLIENT_ID"),
            "tenant_id": os.environ.get("AKS_TENANT_ID"),
            "resource_name": os.environ.get("AKS_RESOURCE_NAME"),
            "resource_group_name": os.environ.get("AKS_RESOURCE_GROUP_NAME"),
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
    pvc = provider.query(command_type="get_pvc")
    node_pressure = provider.query(command_type="get_node_pressure")
    print(pods, pvc, node_pressure)
