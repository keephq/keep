import dataclasses
import datetime

import pydantic
from kubernetes import client
from kubernetes.client.rest import ApiException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class KubernetesProviderAuthConfig:
    """Kubernetes authentication configuration."""

    api_server: pydantic.AnyHttpUrl = dataclasses.field(
        default=None,
        metadata={
            "name": "api_server",
            "description": "The kubernetes api server url",
            "required": True,
            "sensitive": False,
            "validation": "any_http_url"
        },
    )
    token: str = dataclasses.field(
        default=None,
        metadata={
            "name": "token",
            "description": "Bearer token to access kubernetes",
            "required": True,
            "sensitive": True,
        },
    )
    insecure: bool = dataclasses.field(
        default=True,
        metadata={
            "name": "insecure",
            "description": "Skip TLS verification",
            "required": False,
            "sensitive": False,
            "type": "switch"
        },
    )


class KubernetesProvider(BaseProvider):
    """Perform actions like rollout restart objects or list pods on Kubernetes."""

    provider_id: str
    PROVIDER_DISPLAY_NAME = "Kubernetes"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Developer Tools"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_kubernetes",
            description="Check if the provided token can connect to the kubernetes server",
            mandatory=True,
            alias="Connect to the kubernetes",
        )
    ]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.authentication_config = None
        self.validate_config()

    def dispose(self):
        """Dispose the provider."""
        pass

    def validate_config(self):
        """
        Validate the required configuration for the Kubernetes provider.
        """
        if self.config.authentication is None:
            self.config.authentication = {}
        self.authentication_config = KubernetesProviderAuthConfig(
            **self.config.authentication
        )

    def __create_k8s_client(self):
        """
        Create a Kubernetes client.
        """
        client_configuration = client.Configuration()

        client_configuration.host = self.authentication_config.api_server
        client_configuration.verify_ssl = not self.authentication_config.insecure
        client_configuration.api_key = {
            "authorization": "Bearer " + self.authentication_config.token
        }

        return client.ApiClient(client_configuration)

    def validate_scopes(self):
        """
        Validate that the provided token has the required scopes to use the provider.
        """
        self.logger.info("Validating scopes for Kubernetes provider")
        try:
            self.__create_k8s_client()
            self.logger.info("Successfully connected to the Kubernetes server")
            scopes = {
                "connect_to_kubernetes": True,
            }
        except Exception as e:
            self.logger.error(f"Failed to connect to the Kubernetes server: {str(e)}")
            scopes = {
                "connect_to_kubernetes": str(e),
            }

        return scopes

    def _notify(
        self,
        action: str,
        kind: str,
        object_name: str,
        namespace: str,
        labels: str,
        **kwargs,
    ):
        if labels is None:
            labels = []
        if action == "rollout_restart":
            self.__rollout_restart(
                kind=kind, name=object_name, namespace=namespace, labels=labels
            )
        elif action == "list_pods":
            self.__list_pods(namespace=namespace, labels=labels)
        else:
            raise NotImplementedError(f"Action {action} is not implemented")

    def __rollout_restart(self, kind, name, namespace, labels):
        api_client = self.__create_k8s_client()
        self.logger.info(
            f"Performing rollout restart for {kind} {name} using kubernetes provider"
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        now = str(now.isoformat("T") + "Z")
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": now}
                    }
                }
            }
        }
        apps_v1 = client.AppsV1Api(api_client)
        try:
            if kind == "deployment":
                deployment_list = apps_v1.list_namespaced_deployment(
                    namespace=namespace, label_selector=labels
                )
                if not deployment_list.items:
                    raise ValueError(
                        f"Deployment with labels {labels} not found in namespace {namespace}"
                    )
                apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=body
                )
            elif kind == "statefulset":
                statefulset_list = apps_v1.list_namespaced_stateful_set(
                    namespace=namespace, label_selector=labels
                )
                if not statefulset_list.items:
                    raise ValueError(
                        f"StatefulSet with labels {labels} not found in namespace {namespace}"
                    )
                apps_v1.patch_namespaced_stateful_set(
                    name=name, namespace=namespace, body=body
                )
            elif kind == "daemonset":
                daemonset_list = apps_v1.list_namespaced_daemon_set(
                    namespace=namespace, label_selector=labels
                )
                if not daemonset_list.items:
                    raise ValueError(
                        f"DaemonSet with labels {labels} not found in namespace {namespace}"
                    )
                apps_v1.patch_namespaced_daemon_set(
                    name=name, namespace=namespace, body=body
                )
            else:
                raise ValueError(f"Unsupported kind {kind} to perform rollout restart")
        except ApiException as e:
            self.logger.error(
                f"Error performing rollout restart for {kind} {name}: {e}"
            )
            raise Exception(f"Error performing rollout restart for {kind} {name}: {e}")

        self.logger.info(f"Successfully performed rollout restart for {kind} {name}")

    def __list_pods(self, namespace, labels):
        api_client = self.__create_k8s_client()
        core_v1 = client.CoreV1Api(api_client)
        if namespace is None:
            namespace = "default"
        self.logger.info(f"Listing pods in namespace {namespace} with labels {labels}")
        try:
            core_v1.list_namespaced_pod(namespace=namespace, label_selector=labels)
        except ApiException as e:
            self.logger.error(
                f"Error listing pods in namespace {namespace} with labels {labels}: {e}"
            )
            raise Exception(
                f"Error listing pods in namespace {namespace} with labels {labels}: {e}"
            )

        self.logger.info(
            f"Successfully listed pods in namespace {namespace} with labels {labels}"
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    url = os.environ.get("KUBERNETES_URL")
    token = os.environ.get("KUBERNETES_TOKEN")
    insecure = os.environ.get("KUBERNETES_INSECURE", "false").lower() == "true"
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "api_server": url,
            "token": token,
            "insecure": insecure,
        },
    )

    kubernetes_provider = KubernetesProvider(
        context_manager, "kubernetes_keephq", config
    )

    result = kubernetes_provider.notify(
        "rollout_restart", "deployment", "nginx", "default", {"app": "nginx"}
    )
    print(result)
