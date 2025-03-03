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
            "validation": "any_http_url",
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
            "type": "switch",
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

    def _query(self, command_type: str, **kwargs):
        """
        Query Kubernetes resources.
        """
        api_client = self.__create_k8s_client()

        if command_type == "get_logs":
            return self.__get_logs(api_client, **kwargs)
        elif command_type == "get_events":
            return self.__get_events(api_client, **kwargs)
        elif command_type == "get_pods":
            return self.__get_pods(api_client, **kwargs)
        elif command_type == "get_node_pressure":
            return self.__get_node_pressure(api_client, **kwargs)
        elif command_type == "get_pvc":
            return self.__get_pvc(api_client, **kwargs)
        else:
            raise NotImplementedError(f"Command type {command_type} is not implemented")

    def _notify(self, action: str, **kwargs):
        """
        Perform actions on Kubernetes resources.
        """
        if action == "rollout_restart":
            return self.__rollout_restart(**kwargs)
        elif action == "restart_pod":
            return self.__restart_pod(**kwargs)
        else:
            raise NotImplementedError(f"Action {action} is not implemented")

    def __get_logs(
        self,
        api_client,
        namespace,
        pod_name,
        container_name=None,
        tail_lines=100,
        **kwargs,
    ):
        """
        Get logs from a pod.
        """
        self.logger.info(f"Getting logs for pod {pod_name} in namespace {namespace}")
        core_v1 = client.CoreV1Api(api_client)

        try:
            logs = core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=tail_lines,
                pretty=True,
            )
            return logs.splitlines()
        except ApiException as e:
            self.logger.error(f"Error getting logs for pod {pod_name}: {e}")
            raise Exception(f"Error getting logs for pod {pod_name}: {e}")

    def __get_events(self, api_client, namespace, pod_name=None, **kwargs):
        """
        Get events for a namespace or specific pod.
        """
        self.logger.info(
            f"Getting events in namespace {namespace}"
            + (f" for pod {pod_name}" if pod_name else "")
        )

        core_v1 = client.CoreV1Api(api_client)

        try:
            if pod_name:
                # Get the pod to find its UID
                pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                field_selector = f"involvedObject.kind=Pod,involvedObject.name={pod_name},involvedObject.uid={pod.metadata.uid}"
            else:
                field_selector = f"metadata.namespace={namespace}"

            events = core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector,
                sort_by="lastTimestamp",
            )

            # Convert events to dict
            return [event.to_dict() for event in events.items]
        except ApiException as e:
            self.logger.error(f"Error getting events: {e}")
            raise Exception(f"Error getting events: {e}")

    def __get_pods(self, api_client, namespace=None, label_selector=None, **kwargs):
        """
        List pods in a namespace or across all namespaces.
        """
        core_v1 = client.CoreV1Api(api_client)

        try:
            if namespace:
                self.logger.info(f"Listing pods in namespace {namespace}")
                pods = core_v1.list_namespaced_pod(
                    namespace=namespace, label_selector=label_selector
                )
            else:
                self.logger.info("Listing pods across all namespaces")
                pods = core_v1.list_pod_for_all_namespaces(
                    label_selector=label_selector
                )

            return [pod.to_dict() for pod in pods.items]
        except ApiException as e:
            self.logger.error(f"Error listing pods: {e}")
            raise Exception(f"Error listing pods: {e}")

    def __get_node_pressure(self, api_client, **kwargs):
        """
        Get node pressure conditions (Memory, Disk, PID).
        """
        self.logger.info("Getting node pressure conditions")
        core_v1 = client.CoreV1Api(api_client)

        try:
            nodes = core_v1.list_node(watch=False)
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
        except ApiException as e:
            self.logger.error(f"Error getting node pressures: {e}")
            raise Exception(f"Error getting node pressures: {e}")

    def __get_pvc(self, api_client, namespace=None, **kwargs):
        """
        List persistent volume claims in a namespace or across all namespaces.
        """
        core_v1 = client.CoreV1Api(api_client)

        try:
            if namespace:
                self.logger.info(f"Listing PVCs in namespace {namespace}")
                pvcs = core_v1.list_namespaced_persistent_volume_claim(
                    namespace=namespace
                )
            else:
                self.logger.info("Listing PVCs across all namespaces")
                pvcs = core_v1.list_persistent_volume_claim_for_all_namespaces()

            return [pvc.to_dict() for pvc in pvcs.items]
        except ApiException as e:
            self.logger.error(f"Error listing PVCs: {e}")
            raise Exception(f"Error listing PVCs: {e}")

    def __rollout_restart(self, kind, name, namespace, labels=None, **kwargs):
        """
        Perform a rollout restart on a deployment, statefulset, or daemonset.
        """
        api_client = self.__create_k8s_client()
        self.logger.info(
            f"Performing rollout restart for {kind} {name} in namespace {namespace}"
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
            if kind.lower() == "deployment":
                if labels:
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
            elif kind.lower() == "statefulset":
                if labels:
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
            elif kind.lower() == "daemonset":
                if labels:
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
        return {
            "status": "success",
            "message": f"Successfully performed rollout restart for {kind} {name}",
        }

    def __restart_pod(
        self, namespace, pod_name, container_name=None, message=None, **kwargs
    ):
        """
        Restart a pod by deleting it (it will be recreated by its controller).
        This is useful for pods that are in a CrashLoopBackOff state.
        """
        api_client = self.__create_k8s_client()
        core_v1 = client.CoreV1Api(api_client)

        self.logger.info(f"Restarting pod {pod_name} in namespace {namespace}")

        try:
            # Check if the pod exists
            pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)

            # If the pod is managed by a controller, it will be recreated
            # For standalone pods, this will simply delete the pod
            delete_options = client.V1DeleteOptions()
            core_v1.delete_namespaced_pod(
                name=pod_name, namespace=namespace, body=delete_options
            )

            # Return success message
            response_message = (
                message
                if message
                else f"Pod {pod_name} in namespace {namespace} was restarted"
            )
            self.logger.info(response_message)

            return {
                "status": "success",
                "message": response_message,
                "pod_details": {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "containers": [container.name for container in pod.spec.containers],
                },
            }
        except ApiException as e:
            error_message = f"Error restarting pod {pod_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)


if __name__ == "__main__":
    # Output debug messages
    import json
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    url = os.environ.get("KUBERNETES_URL")
    token = os.environ.get("KUBERNETES_TOKEN")
    insecure = os.environ.get("KUBERNETES_INSECURE", "false").lower() == "true"
    namespace = os.environ.get("KUBERNETES_NAMESPACE", "default")
    pod_name = os.environ.get("KUBERNETES_POD_NAME")

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

    # Example queries
    if pod_name:
        print("Getting logs:")
        logs = kubernetes_provider.query(
            command_type="get_logs", namespace=namespace, pod_name=pod_name
        )
        print(logs[:10])  # Print first 10 lines

        print("\nGetting events:")
        events = kubernetes_provider.query(
            command_type="get_events", namespace=namespace, pod_name=pod_name
        )
        print(json.dumps(events[:3], indent=2))  # Print first 3 events

        print("\nRestarting pod:")
        restart_result = kubernetes_provider.notify(
            action="restart_pod",
            namespace=namespace,
            pod_name=pod_name,
            message=f"Manually restarting pod {pod_name}",
        )
        print(json.dumps(restart_result, indent=2))
    else:
        print("Getting pods:")
        pods = kubernetes_provider.query(command_type="get_pods", namespace=namespace)
        print(f"Found {len(pods)} pods in namespace {namespace}")
