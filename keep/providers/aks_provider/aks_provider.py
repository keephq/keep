import dataclasses
import json
import logging
import yaml

import pydantic
from kubernetes import client, config
from azure.identity import ClientSecretCredential
from azure.mgmt.containerservice import ContainerServiceClient

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class AksProviderAuthConfig:
    """AKS authentication configuration."""

    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The service account JSON with container.viewer role",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": ".json",  # this is used to filter the file type in the UI
        }
    )
    cluster_name: str = dataclasses.field(
        metadata={"required": True, "description": "The name of the cluster"}
    )
    resource_group_name: str = dataclasses.field(
        default="us-central1",
        metadata={
            "required": False,
            "description": "The Resource group for the cluster",
            "hint": "MC_resourcegroupname_clustername_location",
        },
    )


class AksProvider(BaseProvider):
    PROVIDER_SCOPES = [
        ProviderScope(
            name="roles/container.viewer",
            description="Read access to AKS resources",
            mandatory=True,
            alias="Kubernetes Engine Viewer",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        try:
            self._service_account_data = json.loads(
                self.authentication_config.service_account_json
            )
            self._sub_id = self._service_account_data.get("sub_id")
            self._azure_client_id = self._service_account_data.get("azure_client_id")
            self._azure_tenant_id = self._service_account_data.get("azure_tenant_id")
            self._azure_client_secret = self._service_account_data.get("azure_client_secret")
        # in case the user didn't provide a service account JSON, we'll later fail it in validate_scopes
        except Exception as e:
            self._service_account_data = None
            self._sub_id = None
        self._cluster_name = self.authentication_config.cluster_name
        self._resource_group_name = self.authentication_config.resource_group_name
        self._client = None

    def dispose(self):
        pass

    def validate_scopes(self):
        """Validate if the service account has the required permissions."""
        if not self._service_account_data or not self._cluster_name or not self._resource_group_name:
            return {"roles/container.viewer": "Service account JSON is invalid"}

        scopes = {}
        # try initializing the client to validate the scopes
        try:
            client = self.client
            scopes["roles/container.viewer"] = True
        except Exception as e:
            if "404" in str(e):
                scopes[
                    "roles/container.viewer"
                ] = "Cluster not found (404 from AKS), please check the cluster name and region"
            elif "403" in str(e):
                scopes["roles/container.viewer"] = "Permission denied (403 from AKS)"
            else:
                scopes["roles/container.viewer"] = str(e)

        return scopes

    def validate_config(self):
        self.authentication_config = AksProviderAuthConfig(**self.config.authentication)

    @property
    def client(self):
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def __generate_client(self):
        # Load service account credentials and create a AKS client
        client_secret_credential = ClientSecretCredential(client_id=self._azure_client_id, client_secret=self._azure_client_secret,tenant_id=self._azure_tenant_id)
        container_service_client = ContainerServiceClient(credential=client_secret_credential, subscription_id=self._sub_id)

        # Fetch the AKS cluster kube config
        kubeconfig = container_service_client.managed_clusters.list_cluster_user_credentials(
            self._resource_group_name,
            self._cluster_name).kubeconfigs[0].value.decode(encoding='UTF-8')
        kubeconfig_dict = yaml.safe_load(kubeconfig)
        config.load_kube_config_from_dict(config_dict=kubeconfig_dict)
        return client.CoreV1Api()

    # Implement other methods to query Kubernetes resources as needed.
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

    # Get these from a secure source or environment variables
    with open("sa.json") as f:
        service_account_data = json.load(f)

    sub_id = service_account_data.get("sub_id")
    resource_group_name = "test-group"
    cluster_name = "test-cluster2"

    config = {
        "authentication": {
            "service_account_json": json.dumps(service_account_data),
            "resource_group_name": resource_group_name,
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
    pvc = provider.query(command_type="get_pvc")
    node_pressure = provider.query(command_type="get_node_pressure")
    print(pods)
