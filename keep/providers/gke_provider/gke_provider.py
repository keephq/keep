import dataclasses
import json
import logging
import tempfile

import pydantic
from google.auth.transport import requests
from google.cloud.container_v1 import ClusterManagerClient
from google.oauth2 import service_account
from kubernetes import client, config

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class GkeProviderAuthConfig:
    """GKE authentication configuration."""

    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The service account JSON with container.developer role",
        }
    )
    cluster_name: str = dataclasses.field(
        metadata={"required": True, "description": "The name of the cluster"}
    )
    region: str = dataclasses.field(
        default="us-central1",
        metadata={"required": False, "description": "The GKE cluster region"},
    )


class GkeProvider(BaseProvider):
    """Enrich alerts with data from GKE."""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._service_account_data = json.loads(
            self.authentication_config.service_account_json
        )
        self._project_id = self._service_account_data.get("project_id")
        self._region = self.authentication_config.region
        self._cluster_name = self.authentication_config.cluster_name
        self._client = None

    def dispose(self):
        pass

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
    cluster_name = "keep-test-cluster"

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
    print(pods)
