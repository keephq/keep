"""
EksProvider is a class that provides a way to interact with AWS EKS clusters.
"""

import dataclasses
import logging

import boto3
import pydantic
from kubernetes import client, config

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class EksProviderAuthConfig:
    """EKS authentication configuration."""

    access_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS access key", "sensitive": True}
    )

    secret_access_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS secret access key",
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

    PROVIDER_DISPLAY_NAME = "Amazon EKS"
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
            eks_client = boto3.client(
                "eks",
                aws_access_key_id=self.authentication_config.access_key,
                aws_secret_access_key=self.authentication_config.secret_access_key,
                region_name=self.authentication_config.region,
            )

            # Test ListClusters permission
            try:
                eks_client.list_clusters()
                scopes["eks:ListClusters"] = True
            except Exception as e:
                scopes["eks:ListClusters"] = str(e)

            # Test DescribeCluster permission
            try:
                eks_client.describe_cluster(
                    name=self.authentication_config.cluster_name
                )
                scopes["eks:DescribeCluster"] = True
            except Exception as e:
                scopes["eks:DescribeCluster"] = str(e)

        except Exception as e:
            self.logger.exception("Error validating AWS EKS scopes")
            for scope in scopes:
                scopes[scope] = str(e)

        return scopes

    @property
    def client(self):
        """Get or create the Kubernetes client for EKS."""
        if self._client is None:
            self._client = self.__generate_client()
        return self._client

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
        """Get a token for EKS authentication."""
        sts_client = boto3.client(
            "sts",
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.secret_access_key,
            region_name=self.authentication_config.region,
        )

        cluster_name = self.authentication_config.cluster_name

        # Generate the presigned url token that EKS will accept
        sts_token = sts_client.get_token(
            ClusterName=cluster_name, DurationSeconds=900  # 15 minutes
        )

        return sts_token["token"]

    def _query(self, command_type: str, **kwargs: dict):
        """Query EKS cluster resources.

        Args:
            command_type: Type of query to execute
            **kwargs: Additional arguments for the query

        Returns:
            Query results based on command type
        """
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

        raise NotImplementedError(f"Command type '{command_type}' not implemented")


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
