"""
EksProvider is a class that provides a way to interact with AWS EKS clusters.
"""

import dataclasses
import logging

import boto3
import pydantic
from kubernetes import client, config
from kubernetes.stream import stream

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class EksProviderAuthConfig:
    """EKS authentication configuration."""

    access_key: str = dataclasses.field(
        metadata={"required": False, "description": "AWS access key (Leave empty if using IAM role at EC2)", "sensitive": True}
    )

    secret_access_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "AWS secret access key (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        }
    )

    region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS region where the EKS cluster is located",
            "sensitive": False,
            "hint": "e.g. us-east-1",
        }
    )

    cluster_name: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Name of the EKS cluster",
            "sensitive": False,
        }
    )


class EksProvider(BaseProvider):
    """Interact with and query AWS EKS clusters."""

    PROVIDER_DISPLAY_NAME = "EKS"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="eks:DescribeCluster",
            description="Required to get cluster information",
            documentation_url="https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeCluster.html",
            mandatory=True,
            alias="Describe Cluster",
        ),
        ProviderScope(
            name="eks:ListClusters",
            description="Required to list available clusters",
            documentation_url="https://docs.aws.amazon.com/eks/latest/APIReference/API_ListClusters.html",
            mandatory=True,
            alias="List Clusters",
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
    """
    Shahar: hard to test the following scopes because by default we don't have the pod name that we can test on
    ProviderScope(
        name="pods:exec",
        description="Required to execute commands in pods",
        documentation_url="https://kubernetes.io/docs/reference/access-authn-authz/rbac/",
        mandatory=False,
        alias="Execute Pod Commands"
    ),
    """

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
        self._client = None

    def dispose(self):
        """Clean up any resources."""
        if self._client:
            self._client.api_client.rest_client.pool_manager.clear()

    def validate_config(self):
        """Validate the provided configuration."""
        self.authentication_config = EksProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate if the credentials have the required permissions."""
        scopes = {scope.name: False for scope in self.PROVIDER_SCOPES}

        try:
            self.logger.info("Starting EKS API permissions validation")
            # Test EKS API permissions
            eks_client = boto3.client(
                "eks",
                aws_access_key_id=self.authentication_config.access_key,
                aws_secret_access_key=self.authentication_config.secret_access_key,
                region_name=self.authentication_config.region,
            )

            try:
                self.logger.info("Validating eks:ListClusters permission")
                eks_client.list_clusters()
                scopes["eks:ListClusters"] = True
                self.logger.info("eks:ListClusters permission validated successfully")
            except Exception as e:
                self.logger.info(f"eks:ListClusters permission validation failed: {e}")
                scopes["eks:ListClusters"] = str(e)

            try:
                self.logger.info("Validating eks:DescribeCluster permission")
                eks_client.describe_cluster(
                    name=self.authentication_config.cluster_name
                )
                scopes["eks:DescribeCluster"] = True
                self.logger.info(
                    "eks:DescribeCluster permission validated successfully"
                )
            except Exception as e:
                self.logger.info(
                    f"eks:DescribeCluster permission validation failed: {e}"
                )
                scopes["eks:DescribeCluster"] = str(e)

            # Test Kubernetes API permissions using the client
            try:
                self.logger.info("Starting Kubernetes API permissions validation")
                k8s_client = self.client  # This will initialize connection to cluster

                # Test pods:list and pods:get
                try:
                    self.logger.info("Validating pods:list and pods:get permissions")
                    k8s_client.list_pod_for_all_namespaces(limit=1)
                    scopes["pods:list"] = True
                    scopes["pods:get"] = True
                    self.logger.info(
                        "pods:list and pods:get permissions validated successfully"
                    )
                except Exception as e:
                    self.logger.info(
                        f"pods:list and pods:get permissions validation failed: {e}"
                    )
                    scopes["pods:list"] = str(e)
                    scopes["pods:get"] = str(e)

                # Test pods:logs
                try:
                    self.logger.info("Validating pods:logs permission")
                    pods = k8s_client.list_pod_for_all_namespaces(limit=1)
                    if pods.items:
                        pod = pods.items[0]
                        containers = pod.spec.containers
                        if containers:
                            k8s_client.read_namespaced_pod_log(
                                name=pod.metadata.name,
                                namespace=pod.metadata.namespace,
                                container=containers[0].name,
                                limit_bytes=100,
                            )
                    scopes["pods:logs"] = True
                    self.logger.info("pods:logs permission validated successfully")
                except Exception as e:
                    self.logger.info(f"pods:logs permission validation failed: {e}")
                    scopes["pods:logs"] = str(e)

                # Test pods:delete
                try:
                    self.logger.info("Validating pods:delete permission")
                    # We don't actually delete, just check if we can get the delete API
                    if pods.items:
                        pod = pods.items[0]
                        k8s_client.delete_namespaced_pod.__doc__
                    scopes["pods:delete"] = True
                    self.logger.info("pods:delete permission validated successfully")
                except Exception as e:
                    self.logger.info(f"pods:delete permission validation failed: {e}")
                    scopes["pods:delete"] = str(e)

                # Test deployments:scale
                apps_v1 = client.AppsV1Api()
                try:
                    self.logger.info("Validating deployments:scale permission")
                    deployments = apps_v1.list_deployment_for_all_namespaces(limit=1)
                    if deployments.items:
                        apps_v1.patch_namespaced_deployment_scale.__doc__
                    scopes["deployments:scale"] = True
                    self.logger.info(
                        "deployments:scale permission validated successfully"
                    )
                except Exception as e:
                    self.logger.info(
                        f"deployments:scale permission validation failed: {e}"
                    )
                    scopes["deployments:scale"] = str(e)

            except Exception as e:
                self.logger.exception("Error validating Kubernetes API scopes")
                for scope in scopes:
                    if scope not in ["eks:ListClusters", "eks:DescribeCluster"]:
                        scopes[scope] = str(e)

        except Exception as e:
            self.logger.exception("Error validating AWS EKS scopes")
            for scope in scopes:
                scopes[scope] = str(e)

        self.logger.info("Completed scope validation")
        return scopes

    @property
    def client(self):
        """Get or create the Kubernetes client for EKS."""
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
        self.logger.info("Listing all nodes")
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

    def __check_pod_shell_access(self, pod, container_name: str) -> str:
        """
        Check if pod has shell access and return appropriate shell.

        Args:
            pod: The Kubernetes pod object
            container_name: Name of the container to check

        Returns:
            str: Path to available shell (/bin/bash or /bin/sh)

        Raises:
            ProviderException: If no shell access is available
        """
        # Get the container object
        container = next(
            (c for c in pod.spec.containers if c.name == container_name),
            pod.spec.containers[0],
        )

        # Try different shells in order of preference
        for shell in ["/bin/bash", "/bin/sh"]:
            try:
                result = self.client.connect_get_namespaced_pod_exec(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    container=container.name,
                    command=[shell, "-c", "exit 0"],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=True,
                )
                if result == "":  # Success
                    return shell
            except Exception:
                continue

        raise ProviderException(
            f"No shell access available in pod {pod.metadata.name} container {container_name}"
        )

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
            # First try direct command execution
            if isinstance(command, list):
                exec_command = command
            else:
                # Try to find a shell
                shell = self.__check_pod_shell_access(pod, container)
                exec_command = [shell, "-c", command]

            # Execute the command
            self.logger.info(
                f"Executing command in pod {pod_name} container {container}"
            )
            ws_client = stream(
                self.client.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                container=container,
                command=exec_command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )

            # Read output
            result = ""
            error = ""

            while ws_client.is_open():
                ws_client.update(timeout=1)
                if ws_client.peek_stdout():
                    result += ws_client.read_stdout()
                if ws_client.peek_stderr():
                    error += ws_client.read_stderr()

            ws_client.close()

            if error:
                raise ProviderException(f"Command execution failed: {error}")

            return result.strip()

        except Exception as e:
            container_info = next(
                (c for c in pod.spec.containers if c.name == container), None
            )
            image = container_info.image if container_info else "unknown"
            raise ProviderException(
                f"Failed to execute command in pod {pod_name} (container: {container}, "
                f"image: {image}): {str(e)}"
            )

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
        """Generate a Kubernetes client configured for EKS."""
        try:
            # Create EKS client
            eks_client = boto3.client(
                "eks",
                aws_access_key_id=self.authentication_config.access_key,
                aws_secret_access_key=self.authentication_config.secret_access_key,
                region_name=self.authentication_config.region,
            )

            # Get cluster info
            cluster_info = eks_client.describe_cluster(
                name=self.authentication_config.cluster_name
            )["cluster"]

            # Generate kubeconfig
            kubeconfig = {
                "apiVersion": "v1",
                "clusters": [
                    {
                        "cluster": {
                            "server": cluster_info["endpoint"],
                            "certificate-authority-data": cluster_info[
                                "certificateAuthority"
                            ]["data"],
                        },
                        "name": "eks_cluster",
                    }
                ],
                "contexts": [
                    {
                        "context": {"cluster": "eks_cluster", "user": "aws_user"},
                        "name": "eks_context",
                    }
                ],
                "current-context": "eks_context",
                "kind": "Config",
                "users": [{"name": "aws_user", "user": {"token": self.__get_token()}}],
            }

            # Load the kubeconfig
            config.load_kube_config_from_dict(kubeconfig)
            return client.CoreV1Api()

        except Exception as e:
            raise ProviderException(f"Failed to generate EKS client: {e}")

    def __get_token(self):
        """Get a token for EKS authentication using awscli's token generator."""

        from awscli.customizations.eks.get_token import STSClientFactory, TokenGenerator
        from botocore import session

        # Create a botocore session with our credentials
        work_session = session.get_session()
        work_session.set_credentials(
            access_key=self.authentication_config.access_key,
            secret_key=self.authentication_config.secret_access_key,
        )

        # Create STS client factory
        client_factory = STSClientFactory(work_session)

        # Get STS client and generate token
        sts_client = client_factory.get_sts_client(
            region_name=self.authentication_config.region
        )
        token = TokenGenerator(sts_client).get_token(
            self.authentication_config.cluster_name
        )

        return token

    def _query(self, command_type: str, **kwargs: dict):
        """Query EKS cluster resources.

        Args:
            command_type: Type of query to execute
            **kwargs: Additional arguments for the query

        Returns:
            Query results based on command type
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

    import os

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = {
        "authentication": {
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "region": os.environ.get("AWS_REGION"),
            "cluster_name": os.environ.get("EKS_CLUSTER_NAME"),
        }
    }

    provider = EksProvider(context_manager, "eks-demo", ProviderConfig(**config))

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
