import dataclasses
import json
import logging

import pydantic
from google.auth.transport import requests
from google.cloud.container_v1 import ClusterManagerClient
from google.oauth2 import service_account
from kubernetes import client, config

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class GkeProviderAuthConfig:
    """GKE authentication configuration."""

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
    region: str = dataclasses.field(
        default="us-central1",
        metadata={
            "required": False,
            "description": "The GKE cluster region",
            "hint": "us-central1",
        },
    )


class GkeProvider(BaseProvider):
    """Enrich alerts with data from GKE."""

    PROVIDER_DISPLAY_NAME = "Google Kubernetes Engine"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="roles/container.viewer",
            description="Read access to GKE resources",
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
            self._project_id = self._service_account_data.get("project_id")
        # in case the user didn't provide a service account JSON, we'll later fail it in validate_scopes
        except Exception:
            self._service_account_data = None
            self._project_id = None
        self._region = self.authentication_config.region
        self._cluster_name = self.authentication_config.cluster_name
        self._client = None

    def dispose(self):
        pass

    def validate_scopes(self):
        """Validate if the service account has the required permissions."""
        if not self._service_account_data or not self._project_id:
            return {"roles/container.viewer": "Service account JSON is invalid"}

        scopes = {}
        # try initializing the client to validate the scopes
        try:
            self.client
            scopes["roles/container.viewer"] = True
        except Exception as e:
            if "404" in str(e):
                scopes["roles/container.viewer"] = (
                    "Cluster not found (404 from GKE), please check the cluster name and region"
                )
            elif "403" in str(e):
                scopes["roles/container.viewer"] = "Permission denied (403 from GKE)"
            else:
                scopes["roles/container.viewer"] = str(e)

        return scopes

    def validate_config(self):
        self.authentication_config = GkeProviderAuthConfig(**self.config.authentication)

    @property
    def client(self):
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def __generate_client(self):
        # Load service account credentials and create a GKE client
        credentials = service_account.Credentials.from_service_account_info(
            self._service_account_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        auth_request = requests.Request()
        credentials.refresh(auth_request)
        gke_client = ClusterManagerClient(credentials=credentials)

        # Fetch the GKE cluster details
        cluster_name = f"projects/{self._project_id}/locations/{self._region}/clusters/{self._cluster_name}"
        cluster = gke_client.get_cluster(name=cluster_name)

        kubeconfig = {
            "apiVersion": "v1",
            "clusters": [
                {
                    "cluster": {
                        "certificate-authority-data": cluster.master_auth.cluster_ca_certificate,
                        "server": f"https://{cluster.endpoint}",
                    },
                    "name": "gke_cluster",
                }
            ],
            "contexts": [
                {
                    "context": {"cluster": "gke_cluster", "user": "gke_user"},
                    "name": "gke_context",
                }
            ],
            "current-context": "gke_context",
            "kind": "Config",
            "users": [
                {
                    "name": "gke_user",
                    "user": {
                        "auth-provider": {
                            "config": {
                                "access-token": credentials.token,
                                "cmd-args": "config config-helper --format=json",
                                "cmd-path": "gcloud",
                                "expiry-key": "token_expiry",
                                "token-key": "access_token",
                            },
                            "name": "gcp",
                        }
                    },
                }
            ],
        }
        config.load_kube_config_from_dict(config_dict=kubeconfig)
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

    project_id = service_account_data.get("project_id")
    region = "us-central1"
    cluster_name = "autopilot-cluster-1"

    config = {
        "authentication": {
            "service_account_json": json.dumps(service_account_data),
            "cluster_name": cluster_name,
            "region": region,
        }
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="gke-demo",
        provider_type="gke",
        provider_config=config,
    )
    # Query GKE resources using the provider's methods.
    pods = provider.query(command_type="get_pods")
    pvc = provider.query(command_type="get_pvc")
    node_pressure = provider.query(command_type="get_node_pressure")
    print(pods)
