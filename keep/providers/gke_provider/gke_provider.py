import dataclasses
import json
import logging

import pydantic
from google.auth.transport import requests
from google.cloud.container_v1 import ClusterManagerClient
from google.oauth2 import service_account
from kubernetes import client, config
from kubernetes.stream import stream

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
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
            "file_type": "application/json",
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
        ProviderScope(
            name="pods:delete",
            description="Required to delete/restart pods",
            documentation_url="https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
            mandatory=False,
            alias="Delete/Restart Pods",
        ),
        ProviderScope(
            name="deployments:scale",
            description="Required to scale deployments",
            documentation_url="https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
            mandatory=False,
            alias="Scale Deployments",
        ),
        ProviderScope(
            name="pods:list",
            description="Required to list pods",
            documentation_url="https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
            mandatory=False,
            alias="List Pods",
        ),
        ProviderScope(
            name="pods:get",
            description="Required to get pod details",
            documentation_url="https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
            mandatory=False,
            alias="Get Pod Details",
        ),
        ProviderScope(
            name="pods:logs",
            description="Required to get pod logs",
            documentation_url="https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
            mandatory=False,
            alias="Get Pod Logs",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="List Pods",
            func_name="get_pods",
            scopes=["pods:list", "pods:get"],
            description="List all pods in a namespace or across all namespaces",
            type="view",
        ),
        ProviderMethod(
            name="List Persistent Volume Claims",
            func_name="get_pvc",
            scopes=["pods:list"],
            description="List all PVCs in a namespace or across all namespaces",
            type="view",
        ),
        ProviderMethod(
            name="Get Node Pressure",
            func_name="get_node_pressure",
            scopes=["pods:list"],
            description="Get pressure metrics for all nodes",
            type="view",
        ),
        ProviderMethod(
            name="Execute Command",
            func_name="exec_command",
            scopes=["pods:exec"],
            description="Execute a command in a pod",
            type="action",
        ),
        ProviderMethod(
            name="Restart Pod",
            func_name="restart_pod",
            scopes=["pods:delete"],
            description="Restart a pod by deleting it",
            type="action",
        ),
        ProviderMethod(
            name="Get Deployment",
            func_name="get_deployment",
            scopes=["pods:list"],
            description="Get deployment information",
            type="view",
        ),
        ProviderMethod(
            name="Scale Deployment",
            func_name="scale_deployment",
            scopes=["deployments:scale"],
            description="Scale a deployment to specified replicas",
            type="action",
        ),
        ProviderMethod(
            name="Get Pod Logs",
            func_name="get_pod_logs",
            scopes=["pods:logs"],
            description="Get logs from a pod",
            type="view",
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
        except Exception:
            self._service_account_data = None
            self._project_id = None
        self._region = self.authentication_config.region
        self._cluster_name = self.authentication_config.cluster_name
        self._client = None

    def dispose(self):
        """Clean up any resources."""
        if self._client:
            self._client.api_client.rest_client.pool_manager.clear()

    def validate_config(self):
        """Validate the provided configuration."""
        self.authentication_config = GkeProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate if the service account has the required permissions."""
        if not self._service_account_data or not self._project_id:
            return {"roles/container.viewer": "Service account JSON is invalid"}

        scopes = {scope.name: False for scope in self.PROVIDER_SCOPES}

        try:
            # Test GKE API permissions
            credentials = service_account.Credentials.from_service_account_info(
                self._service_account_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            auth_request = requests.Request()
            credentials.refresh(auth_request)
            gke_client = ClusterManagerClient(credentials=credentials)

            try:
                cluster_name = f"projects/{self._project_id}/locations/{self._region}/clusters/{self._cluster_name}"
                gke_client.get_cluster(name=cluster_name)
                scopes["roles/container.viewer"] = True
            except Exception as e:
                if "404" in str(e):
                    scopes["roles/container.viewer"] = (
                        "Cluster not found (404 from GKE), please check the cluster name and region"
                    )
                elif "403" in str(e):
                    scopes["roles/container.viewer"] = (
                        "Permission denied (403 from GKE)"
                    )
                else:
                    scopes["roles/container.viewer"] = str(e)

            # Test Kubernetes API permissions
            try:
                k8s_client = self.client

                # Test pods:list and pods:get
                try:
                    k8s_client.list_pod_for_all_namespaces(limit=1)
                    scopes["pods:list"] = True
                    scopes["pods:get"] = True
                except Exception as e:
                    scopes["pods:list"] = str(e)
                    scopes["pods:get"] = str(e)

                # Test pods:logs
                try:
                    pods = k8s_client.list_pod_for_all_namespaces(limit=1)
                    if pods.items:
                        pod = pods.items[0]
                        k8s_client.read_namespaced_pod_log(
                            name=pod.metadata.name,
                            namespace=pod.metadata.namespace,
                            container=pod.spec.containers[0].name,
                            limit_bytes=100,
                        )
                    scopes["pods:logs"] = True
                except Exception as e:
                    scopes["pods:logs"] = str(e)

                # Test pods:delete
                try:
                    if pods.items:
                        pod = pods.items[0]
                        k8s_client.delete_namespaced_pod.__doc__
                    scopes["pods:delete"] = True
                except Exception as e:
                    scopes["pods:delete"] = str(e)

                # Test deployments:scale
                apps_v1 = client.AppsV1Api()
                try:
                    deployments = apps_v1.list_deployment_for_all_namespaces(limit=1)
                    if deployments.items:
                        apps_v1.patch_namespaced_deployment_scale.__doc__
                    scopes["deployments:scale"] = True
                except Exception as e:
                    scopes["deployments:scale"] = str(e)

            except Exception as e:
                for scope in scopes:
                    if scope != "roles/container.viewer":
                        scopes[scope] = str(e)

        except Exception as e:
            for scope in scopes:
                scopes[scope] = str(e)

        return scopes

    @property
    def client(self):
        """Get or create the Kubernetes client for GKE."""
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

    def get_pods(self, namespace: str = None) -> list:
        """List all pods in a namespace or across all namespaces."""
        if namespace:
            self.logger.info(f"Listing pods in namespace {namespace}")
            pods = self.client.list_namespaced_pod(namespace=namespace)
        else:
            self.logger.info("Listing pods across all namespaces")
            pods = self.client.list_pod_for_all_namespaces()
        return [pod.to_dict() for pod in pods.items]

    def get_pvc(self, namespace: str = None) -> list:
        """List all PVCs in a namespace or across all namespaces."""
        if namespace:
            self.logger.info(f"Listing PVCs in namespace {namespace}")
            pvcs = self.client.list_namespaced_persistent_volume_claim(
                namespace=namespace
            )
        else:
            self.logger.info("Listing PVCs across all namespaces")
            pvcs = self.client.list_persistent_volume_claim_for_all_namespaces()
        return [pvc.to_dict() for pvc in pvcs.items]

    def get_node_pressure(self) -> list:
        """Get pressure metrics for all nodes."""
        self.logger.info("Getting node pressure metrics")
        nodes = self.client.list_node()
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

    def exec_command(
        self, namespace: str, pod_name: str, command: str, container: str = None
    ) -> str:
        """Execute a command in a pod."""
        if not all([namespace, pod_name]):
            raise ProviderException(
                "namespace and pod_name are required for exec_command"
            )

        # Get the pod
        self.logger.info(f"Reading pod {pod_name} in namespace {namespace}")
        pod = self.client.read_namespaced_pod(name=pod_name, namespace=namespace)

        # If container not specified, use first container
        if not container:
            container = pod.spec.containers[0].name

        try:
            # Execute the command
            self.logger.info(
                f"Executing command in pod {pod_name} container {container}"
            )
            exec_command = (
                ["/bin/sh", "-c", command] if isinstance(command, str) else command
            )
            result = stream(
                self.client.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                container=container,
                command=exec_command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
            return result

        except Exception as e:
            raise ProviderException(f"Failed to execute command: {str(e)}")

    def restart_pod(self, namespace: str, pod_name: str):
        """Restart a pod by deleting it."""
        if not all([namespace, pod_name]):
            raise ProviderException(
                "namespace and pod_name are required for restart_pod"
            )

        self.logger.info(f"Deleting pod {pod_name} in namespace {namespace}")
        return self.client.delete_namespaced_pod(name=pod_name, namespace=namespace)

    def get_deployment(self, deployment_name: str, namespace: str = "default"):
        """Get deployment information."""
        if not deployment_name:
            raise ProviderException("deployment_name is required for get_deployment")

        apps_v1 = client.AppsV1Api()
        try:
            deployment = apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=namespace
            )
            return deployment.to_dict()
        except Exception as e:
            raise ProviderException(f"Failed to get deployment info: {str(e)}")

    def scale_deployment(self, namespace: str, deployment_name: str, replicas: int):
        """Scale a deployment to specified replicas."""
        if not all([namespace, deployment_name, replicas is not None]):
            raise ProviderException(
                "namespace, deployment_name and replicas are required for scale_deployment"
            )

        apps_v1 = client.AppsV1Api()
        self.logger.info(
            f"Scaling deployment {deployment_name} in namespace {namespace} to {replicas} replicas"
        )
        return apps_v1.patch_namespaced_deployment_scale(
            name=deployment_name,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )

    def get_pod_logs(
        self,
        namespace: str,
        pod_name: str,
        container: str = None,
        tail_lines: int = 100,
    ):
        """Get logs from a pod."""
        if not all([namespace, pod_name]):
            raise ProviderException(
                "namespace and pod_name are required for get_pod_logs"
            )

        self.logger.info(f"Getting logs for pod {pod_name} in namespace {namespace}")
        return self.client.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
        )

    def __generate_client(self):
        """Generate a Kubernetes client configured for GKE."""
        try:
            # Create GKE client with credentials
            credentials = service_account.Credentials.from_service_account_info(
                self._service_account_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            auth_request = requests.Request()
            credentials.refresh(auth_request)
            gke_client = ClusterManagerClient(credentials=credentials)

            # Get cluster details
            cluster_name = f"projects/{self._project_id}/locations/{self._region}/clusters/{self._cluster_name}"
            cluster = gke_client.get_cluster(name=cluster_name)

            # Generate kubeconfig
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

            # Load kubeconfig
            config.load_kube_config_from_dict(config_dict=kubeconfig)
            return client.CoreV1Api()

        except Exception as e:
            raise ProviderException(f"Failed to generate GKE client: {e}")

    def _query(self, command_type: str, **kwargs: dict):
        """Query GKE cluster resources.

        Args:
            command_type: Type of query to execute
            **kwargs: Additional arguments for the query

        Returns:
            Query results based on command type

        Raises:
            NotImplementedError: If command type is not implemented
        """
        # Map command types to provider methods
        command_map = {
            "get_pods": self.get_pods,
            "get_pvc": self.get_pvc,
            "get_node_pressure": self.get_node_pressure,
            "exec_command": self.exec_command,
            "restart_pod": self.restart_pod,
            "get_deployment": self.get_deployment,
            "scale_deployment": self.scale_deployment,
            "get_pod_logs": self.get_pod_logs,
        }

        if command_type not in command_map:
            raise NotImplementedError(f"Command type '{command_type}' not implemented")

        method = command_map[command_type]
        return method(**kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Get service account JSON from file
    with open("sa.json") as f:
        service_account_data = json.load(f)

    config = {
        "authentication": {
            "service_account_json": json.dumps(service_account_data),
            "cluster_name": "my-gke-cluster",
            "region": "us-central1",
        }
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="gke-demo",
        provider_type="gke",
        provider_config=config,
    )

    # Test the provider
    print("Validating scopes...")
    scopes = provider.validate_scopes()
    print(f"Scopes: {scopes}")

    print("\nQuerying pods...")
    pods = provider.query(command_type="get_pods")
    print(f"Found {len(pods)} pods")

    print("\nQuerying PVCs...")
    pvcs = provider.query(command_type="get_pvc")
    print(f"Found {len(pvcs)} PVCs")

    print("\nQuerying node pressures...")
    pressures = provider.query(command_type="get_node_pressure")
    print(f"Found pressure info for {len(pressures)} nodes")
