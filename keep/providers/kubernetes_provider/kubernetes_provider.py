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
        Args:
            command_type (str): The type of query to perform. Supported queries are:
                - get_logs: Get logs from a pod
                - get_deployment_logs: Get logs from all pods in a deployment
                - get_events: Get events for a namespace or pod
                - get_nodes: List nodes
                - get_pods: List pods
                - get_node_pressure: Get node pressure conditions
                - get_pvc: List persistent volume claims
                - get_deployments: List deployments
                - get_statefulsets: List statefulsets
                - get_daemonsets: List daemonsets
                - get_services: List services
                - get_namespaces: List namespaces
                - get_ingresses: List ingresses for a namespace or all namespaces
                - get_jobs: List jobs
            **kwargs: Additional arguments for the query.
        """
        api_client = self.__create_k8s_client()

        if command_type == "get_logs":
            return self.__get_logs(api_client, **kwargs)
        elif command_type == "get_deployment_logs":
            return self.__get_deployment_logs(api_client, **kwargs)
        elif command_type == "get_events":
            return self.__get_events(api_client, **kwargs)
        elif command_type == "get_nodes":
            return self.__get_nodes(api_client, **kwargs)
        elif command_type == "get_pods":
            return self.__get_pods(api_client, **kwargs)
        elif command_type == "get_node_pressure":
            return self.__get_node_pressure(api_client, **kwargs)
        elif command_type == "get_pvc":
            return self.__get_pvc(api_client, **kwargs)
        elif command_type == "get_services":
            return self.__get_services(api_client, **kwargs)
        elif command_type == "get_deployments":
            return self.__get_deployments(api_client, **kwargs)
        elif command_type == "get_daemonsets":
            return self.__get_daemonsets(api_client, **kwargs)
        elif command_type == "get_statefulsets":
            return self.__get_statefulsets(api_client, **kwargs)
        elif command_type == "get_namespaces":
            return self.__get_namespaces(api_client, **kwargs)
        elif command_type == "get_ingresses":
            return self.__get_ingresses(api_client, **kwargs)
        elif command_type == "get_jobs":
            return self.__get_jobs(api_client, **kwargs)

        else:
            raise NotImplementedError(f"Command type {command_type} is not implemented")

    def _notify(self, action: str, **kwargs):
        """
        Perform actions on Kubernetes resources.
        Args:
            action (str): The action to perform. Supported actions are:
                - rollout_restart: Restart a deployment/statefulset/daemonset
                - restart_pod: Restart a specific pod
                - cordon_node: Mark node as unschedulable
                - uncordon_node: Mark node as schedulable
                - drain_node: Safely evict pods from node
                - scale_deployment: Scale deployment up/down
                - scale_statefulset: Scale statefulset up/down
                - exec_pod_command: Execute command in pod
            **kwargs: Additional arguments for the action.
        """
        if action == "rollout_restart":
            return self.__rollout_restart(**kwargs)
        elif action == "restart_pod":
            return self.__restart_pod(**kwargs)
        elif action == "cordon_node":
            return self.__cordon_node(**kwargs)
        elif action == "uncordon_node":
            return self.__uncordon_node(**kwargs)
        elif action == "drain_node":
            return self.__drain_node(**kwargs)
        elif action == "scale_deployment":
            return self.__scale_deployment(**kwargs)
        elif action == "scale_statefulset":
            return self.__scale_statefulset(**kwargs)
        elif action == "exec_pod_command":
            return self.__exec_pod_command(**kwargs)
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
        except UnicodeEncodeError:
            logs = core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=tail_lines,
            )
            return logs.splitlines()
        except ApiException as e:
            self.logger.error(f"Error getting logs for pod {pod_name}: {e}")
            raise Exception(f"Error getting logs for pod {pod_name}: {e}")

    def __get_deployment_logs(
        self,
        api_client,
        namespace,
        deployment_name,
        container_name=None,
        tail_lines=100,
        **kwargs,
    ):
        """
        Get logs from all pods in a deployment.
        """
        self.logger.info(f"Getting logs for deployment {deployment_name} in namespace {namespace}")
        
        # First get pods for the deployment
        core_v1 = client.CoreV1Api(api_client)
        apps_v1 = client.AppsV1Api(api_client)
        
        try:
            # Get deployment to find its selector
            deployment = apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=namespace
            )
            
            # Build label selector from deployment's selector
            match_labels = deployment.spec.selector.match_labels
            label_selector = ",".join([f"{k}={v}" for k, v in match_labels.items()])
            
            # Get pods matching the selector
            pods = core_v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )
            
            deployment_logs = {}
            
            for pod in pods.items:
                pod_name = pod.metadata.name
                try:
                    logs = core_v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container_name,
                        tail_lines=tail_lines,
                        pretty=True,
                    )
                    deployment_logs[pod_name] = logs.splitlines()
                except UnicodeEncodeError:
                    logs = core_v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container_name,
                        tail_lines=tail_lines,
                    )
                    deployment_logs[pod_name] = logs.splitlines()
                except ApiException as pod_e:
                    self.logger.warning(f"Could not get logs for pod {pod_name}: {pod_e}")
                    deployment_logs[pod_name] = [f"Error getting logs: {pod_e}"]
            
            return deployment_logs
            
        except ApiException as e:
            self.logger.error(f"Error getting deployment logs for {deployment_name}: {e}")
            raise Exception(f"Error getting deployment logs for {deployment_name}: {e}")

    def __get_events(
        self, api_client, namespace, pod_name=None, sort_by=None, **kwargs
    ):
        """
        Get events for a namespace or specific pod.
        """
        self.logger.info(
            f"Getting events in namespace {namespace}"
            + (f" for pod {pod_name}" if pod_name else ""),
            extra={
                "pod_name": pod_name,
                "namespace": namespace,
                "sort_by": sort_by,
                "tenant_id": self.context_manager.tenant_id,
                "workflow_id": self.context_manager.workflow_id,
            },
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
            )

            if sort_by:
                self.logger.info(
                    f"Sorting events by {sort_by}",
                    extra={"sort_by": sort_by, "events_count": len(events.items)},
                )
                try:
                    sorted_events = sorted(
                        events.items,
                        key=lambda event: getattr(event, sort_by, None),
                        reverse=True,
                    )
                    return sorted_events
                except Exception:
                    self.logger.exception(
                        f"Error sorting events by {sort_by}",
                        extra={
                            "sort_by": sort_by,
                            "events_count": len(events.items),
                            "tenant_id": self.context_manager.tenant_id,
                            "workflow_id": self.context_manager.workflow_id,
                        },
                    )

            # Convert events to dict
            return [event.to_dict() for event in events.items]
        except ApiException as e:
            self.logger.exception(
                "Error getting events",
                extra={
                    "tenant_id": self.context_manager.tenant_id,
                    "workflow_id": self.context_manager.workflow_id,
                },
            )
            raise Exception(f"Error getting events: {e}") from e

    def __get_nodes(self, api_client, label_selector=None, return_full=False, **kwargs):
        """
        List all nodes in the cluster.

        Args:
            return_full (bool): If True, return full node objects as dicts.
                                If False (default), return only basic info.
        """
        self.logger.info("Listing all nodes in the cluster")
        core_v1 = client.CoreV1Api(api_client)

        try:
            nodes = core_v1.list_node(label_selector=label_selector)
            if return_full:
                return [node.to_dict() for node in nodes.items]
            else:
                # Return basic info: name, status, labels
                basic_info = []
                for node in nodes.items:
                    info = {
                        "name": node.metadata.name,
                        "labels": node.metadata.labels,
                        "status": node.status.conditions[-1].type if node.status.conditions else None,
                        "addresses": [addr.address for addr in node.status.addresses] if node.status.addresses else [],
                    }
                    basic_info.append(info)
                return basic_info
        except ApiException as e:
            self.logger.error(f"Error listing nodes: {e}")
            raise Exception(f"Error listing nodes: {e}")

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

    def __get_services(self, api_client, namespace=None, return_full=False, **kwargs):
        """
        List services in a namespace or across all namespaces.

        Args:
            return_full (bool): If True, return full service objects as dicts.
                                If False (default), return only the service names.
        """
        core_v1 = client.CoreV1Api(api_client)

        try:
            if namespace:
                self.logger.info(f"Listing services in namespace {namespace}")
                services = core_v1.list_namespaced_service(namespace=namespace)
            else:
                self.logger.info("Listing services across all namespaces")
                services = core_v1.list_service_for_all_namespaces()

            if return_full:
                # Sanitize the services data to ensure JSON serialization
                sanitized_services = []
                for service in services.items:
                    service_dict = service.to_dict()

                    # Convert any datetime objects to strings
                    def sanitize_dict(obj):
                        if isinstance(obj, dict):
                            return {k: sanitize_dict(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [sanitize_dict(item) for item in obj]
                        elif hasattr(obj, 'isoformat'):  # datetime objects
                            return obj.isoformat()
                        elif obj is None:
                            return None
                        else:
                            return obj

                    sanitized_service = sanitize_dict(service_dict)
                    sanitized_services.append(sanitized_service)

                return sanitized_services
            else:
                # Return only service names
                return [service.metadata.name for service in services.items]
        except ApiException as e:
            self.logger.error(f"Error listing services: {e}")
            raise Exception(f"Error listing services: {e}")

    def __get_deployments(self, api_client, namespace=None, return_full=False, **kwargs):
        """
        List deployments in a namespace or across all namespaces.
        """
        apps_v1 = client.AppsV1Api(api_client)

        try:
            if namespace:
                self.logger.info(f"Listing deployments in namespace {namespace}")
                deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
            else:
                self.logger.info("Listing deployments across all namespaces")
                deployments = apps_v1.list_deployment_for_all_namespaces()

            if return_full:
                return [deployment.to_dict() for deployment in deployments.items]
            else:
                return [deployment.metadata.name for deployment in deployments.items]
        except ApiException as e:
            self.logger.error(f"Error listing deployments: {e}")
            raise Exception(f"Error listing deployments: {e}")

    def __get_statefulsets(self, api_client, namespace=None, return_full=False, **kwargs):
        """
        List statefulsets in a namespace or across all namespaces.
        """
        apps_v1 = client.AppsV1Api(api_client)
        try:
            if namespace:
                self.logger.info(f"Listing statefulsets in namespace {namespace}")
                statefulsets = apps_v1.list_namespaced_stateful_set(namespace=namespace)
            else:
                self.logger.info("Listing statefulsets across all namespaces")
                statefulsets = apps_v1.list_stateful_set_for_all_namespaces()
            if return_full:
                return [statefulset.to_dict() for statefulset in statefulsets.items]
            else:
                return [statefulset.metadata.name for statefulset in statefulsets.items]
        except ApiException as e:
            self.logger.error(f"Error listing statefulsets: {e}")
            raise Exception(f"Error listing statefulsets: {e}")

    def __get_daemonsets(self, api_client, namespace=None, return_full=False, **kwargs):
        """
        List daemonsets in a namespace or across all namespaces.
        """
        apps_v1 = client.AppsV1Api(api_client)
        try:
            if namespace:
                self.logger.info(f"Listing daemonsets in namespace {namespace}")
                daemonsets = apps_v1.list_namespaced_daemon_set(namespace=namespace)
            else:
                self.logger.info("Listing daemonsets across all namespaces")
                daemonsets = apps_v1.list_daemon_set_for_all_namespaces()
        except ApiException as e:
            self.logger.error(f"Error listing daemonsets: {e}")
            raise Exception(f"Error listing daemonsets: {e}")

        if return_full:
            return [daemonset.to_dict() for daemonset in daemonsets.items]
        else:
            return [daemonset.metadata.name for daemonset in daemonsets.items]


    def __get_namespaces(self, api_client, return_full=False, **kwargs):
        """
        List all namespaces.

        Args:
            return_full (bool): If True, return full namespace objects as dicts.
                                If False (default), return only the names.
        """
        self.logger.info("Listing namespaces")
        core_v1 = client.CoreV1Api(api_client)

        try:
            namespaces = core_v1.list_namespace()
            if return_full:
                return [namespace.to_dict() for namespace in namespaces.items]
            else:
                return [namespace.metadata.name for namespace in namespaces.items]
        except ApiException as e:
            self.logger.error(f"Error listing namespaces: {e}")
            raise Exception(f"Error listing namespaces: {e}")

    def __get_ingresses(self, api_client, namespace=None, return_full=False, **kwargs):
        """
        List ingresses in a namespace or across all namespaces.

        Args:
            return_full (bool): If True, return full ingress objects as dicts.
                                If False (default), return only the names.
        """
        networking_v1 = client.NetworkingV1Api(api_client)

        try:
            if namespace:
                self.logger.info(f"Listing ingresses in namespace {namespace}")
                ingresses = networking_v1.list_namespaced_ingress(namespace=namespace)
            else:
                self.logger.info("Listing ingresses across all namespaces")
                ingresses = networking_v1.list_ingress_for_all_namespaces()

            if return_full:
                return [ingress.to_dict() for ingress in ingresses.items]
            else:
                return [ingress.metadata.name for ingress in ingresses.items]
        except ApiException as e:
            self.logger.error(f"Error listing ingresses: {e}")
            raise Exception(f"Error listing ingresses: {e}")

    def __get_jobs(self, api_client, namespace=None, return_full=False, **kwargs):
        """
        List jobs in a namespace or across all namespaces.

        Args:
            return_full (bool): If True, return full job objects as dicts.
                                If  False (default), return only the names.
        """

        batch_v1 = client.BatchV1Api(api_client)

        try:
            if namespace:
                self.logger.info(f"Listing jobs in namespace {namespace}")
                jobs = batch_v1.list_namespaced_job(namespace=namespace)
            else:
                self.logger.info("Listing jobs across all namespaces")
                jobs = batch_v1.list_job_for_all_namespaces()

            if return_full:
                return [job.to_dict() for job in jobs.items]
            else:
                return [job.metadata.name for job in jobs.items]
        except ApiException as e:
            self.logger.error(f"Error listing jobs: {e}")
            raise Exception(f"Error listing jobs: {e}")


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

    def __cordon_node(self, node_name, **kwargs):
        """
        Mark a node as unschedulable (cordon).
        """
        api_client = self.__create_k8s_client()
        core_v1 = client.CoreV1Api(api_client)
        
        self.logger.info(f"Cordoning node {node_name}")
        
        try:
            # Get the node
            node = core_v1.read_node(name=node_name)
            
            # Update the node to be unschedulable
            node.spec.unschedulable = True
            
            # Patch the node
            core_v1.patch_node(name=node_name, body=node)
            
            self.logger.info(f"Successfully cordoned node {node_name}")
            return {
                "status": "success",
                "message": f"Node {node_name} has been cordoned (marked unschedulable)",
            }
        except ApiException as e:
            error_message = f"Error cordoning node {node_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def __uncordon_node(self, node_name, **kwargs):
        """
        Mark a node as schedulable (uncordon).
        """
        api_client = self.__create_k8s_client()
        core_v1 = client.CoreV1Api(api_client)
        
        self.logger.info(f"Uncordoning node {node_name}")
        
        try:
            # Get the node
            node = core_v1.read_node(name=node_name)
            
            # Update the node to be schedulable
            node.spec.unschedulable = False
            
            # Patch the node
            core_v1.patch_node(name=node_name, body=node)
            
            self.logger.info(f"Successfully uncordoned node {node_name}")
            return {
                "status": "success",
                "message": f"Node {node_name} has been uncordoned (marked schedulable)",
            }
        except ApiException as e:
            error_message = f"Error uncordoning node {node_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def __drain_node(self, node_name, force=False, ignore_daemonsets=True, delete_emptydir_data=False, **kwargs):
        """
        Safely evict pods from a node (drain).
        """
        api_client = self.__create_k8s_client()
        core_v1 = client.CoreV1Api(api_client)
        
        self.logger.info(f"Draining node {node_name}")
        
        try:
            # First cordon the node
            self.__cordon_node(node_name)
            
            # Get all pods on the node
            field_selector = f"spec.nodeName={node_name}"
            pods = core_v1.list_pod_for_all_namespaces(field_selector=field_selector)
            
            evicted_pods = []
            failed_pods = []
            
            for pod in pods.items:
                # Skip pods that are already terminating
                if pod.metadata.deletion_timestamp:
                    continue
                    
                # Skip DaemonSet pods if ignore_daemonsets is True
                if ignore_daemonsets:
                    owner_references = pod.metadata.owner_references or []
                    is_daemonset_pod = any(
                        ref.kind == "DaemonSet" for ref in owner_references
                    )
                    if is_daemonset_pod:
                        continue
                
                # Skip pods with emptyDir volumes unless explicitly allowed
                if not delete_emptydir_data:
                    volumes = pod.spec.volumes or []
                    has_emptydir = any(
                        vol.empty_dir is not None for vol in volumes
                    )
                    if has_emptydir and not force:
                        failed_pods.append({
                            "name": pod.metadata.name,
                            "namespace": pod.metadata.namespace,
                            "reason": "Has emptyDir volumes (use delete_emptydir_data=True to override)"
                        })
                        continue
                
                try:
                    # Create eviction object
                    eviction = client.V1Eviction(
                        metadata=client.V1ObjectMeta(
                            name=pod.metadata.name,
                            namespace=pod.metadata.namespace
                        )
                    )
                    
                    # Evict the pod
                    core_v1.create_namespaced_pod_eviction(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                        body=eviction
                    )
                    
                    evicted_pods.append({
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace
                    })
                    
                except ApiException as e:
                    if e.status == 429:  # Too Many Requests - PodDisruptionBudget
                        if force:
                            # Force delete the pod if force is True
                            try:
                                core_v1.delete_namespaced_pod(
                                    name=pod.metadata.name,
                                    namespace=pod.metadata.namespace,
                                    grace_period_seconds=0
                                )
                                evicted_pods.append({
                                    "name": pod.metadata.name,
                                    "namespace": pod.metadata.namespace,
                                    "forced": True
                                })
                            except ApiException as delete_e:
                                failed_pods.append({
                                    "name": pod.metadata.name,
                                    "namespace": pod.metadata.namespace,
                                    "reason": f"Could not force delete: {delete_e}"
                                })
                        else:
                            failed_pods.append({
                                "name": pod.metadata.name,
                                "namespace": pod.metadata.namespace,
                                "reason": f"Blocked by PodDisruptionBudget (use force=True to override): {e}"
                            })
                    else:
                        failed_pods.append({
                            "name": pod.metadata.name,
                            "namespace": pod.metadata.namespace,
                            "reason": str(e)
                        })
            
            result = {
                "status": "success" if not failed_pods else "partial_success",
                "message": f"Node {node_name} drain completed",
                "evicted_pods": evicted_pods,
                "failed_pods": failed_pods,
                "summary": {
                    "total_evicted": len(evicted_pods),
                    "total_failed": len(failed_pods)
                }
            }
            
            self.logger.info(f"Drain completed for node {node_name}: {len(evicted_pods)} evicted, {len(failed_pods)} failed")
            return result
            
        except ApiException as e:
            error_message = f"Error draining node {node_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def __scale_deployment(self, namespace, deployment_name, replicas, **kwargs):
        """
        Scale a deployment to the specified number of replicas.
        """
        api_client = self.__create_k8s_client()
        apps_v1 = client.AppsV1Api(api_client)
        
        self.logger.info(f"Scaling deployment {deployment_name} in namespace {namespace} to {replicas} replicas")
        
        try:
            # Get current deployment
            deployment = apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=namespace
            )
            
            current_replicas = deployment.spec.replicas
            
            # Update replicas
            deployment.spec.replicas = replicas
            
            # Patch the deployment
            apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment
            )
            
            self.logger.info(f"Successfully scaled deployment {deployment_name} from {current_replicas} to {replicas} replicas")
            return {
                "status": "success",
                "message": f"Deployment {deployment_name} scaled from {current_replicas} to {replicas} replicas",
                "previous_replicas": current_replicas,
                "new_replicas": replicas,
            }
        except ApiException as e:
            error_message = f"Error scaling deployment {deployment_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def __scale_statefulset(self, namespace, statefulset_name, replicas, **kwargs):
        """
        Scale a statefulset to the specified number of replicas.
        """
        api_client = self.__create_k8s_client()
        apps_v1 = client.AppsV1Api(api_client)
        
        self.logger.info(f"Scaling statefulset {statefulset_name} in namespace {namespace} to {replicas} replicas")
        
        try:
            # Get current statefulset
            statefulset = apps_v1.read_namespaced_stateful_set(
                name=statefulset_name, namespace=namespace
            )
            
            current_replicas = statefulset.spec.replicas
            
            # Update replicas
            statefulset.spec.replicas = replicas
            
            # Patch the statefulset
            apps_v1.patch_namespaced_stateful_set(
                name=statefulset_name,
                namespace=namespace,
                body=statefulset
            )
            
            self.logger.info(f"Successfully scaled statefulset {statefulset_name} from {current_replicas} to {replicas} replicas")
            return {
                "status": "success",
                "message": f"StatefulSet {statefulset_name} scaled from {current_replicas} to {replicas} replicas",
                "previous_replicas": current_replicas,
                "new_replicas": replicas,
            }
        except ApiException as e:
            error_message = f"Error scaling statefulset {statefulset_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def __exec_pod_command(self, namespace, pod_name, command, container_name=None, **kwargs):
        """
        Execute a command inside a pod.
        """
        api_client = self.__create_k8s_client()
        core_v1 = client.CoreV1Api(api_client)
        
        self.logger.info(f"Executing command in pod {pod_name} in namespace {namespace}: {command}")
        
        try:
            from kubernetes.stream import stream
            
            # Prepare the command
            if isinstance(command, str):
                # Split command string into list
                exec_command = ['/bin/sh', '-c', command]
            else:
                exec_command = command
            
            # Execute the command
            resp = stream(
                core_v1.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                command=exec_command,
                container=container_name,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False
            )
            
            # Read the output
            output = ""
            error = ""
            
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    output += resp.read_stdout()
                if resp.peek_stderr():
                    error += resp.read_stderr()
            
            resp.close()
            
            result = {
                "status": "success",
                "command": command,
                "stdout": output,
                "stderr": error,
                "pod_name": pod_name,
                "namespace": namespace,
                "container": container_name,
            }
            
            self.logger.info(f"Successfully executed command in pod {pod_name}")
            return result
            
        except ApiException as e:
            error_message = f"Error executing command in pod {pod_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)
        except Exception as e:
            error_message = f"Error executing command in pod {pod_name}: {e}"
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
    deployment_name = os.environ.get("KUBERNETES_DEPLOYMENT_NAME")

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
        try:
            logs = kubernetes_provider.query(
                command_type="get_logs", namespace=namespace, pod_name=pod_name
            )
            print(logs[:10])  # Print first 10 lines
        except Exception as e:
            print(f"Error: {e}")

        print("\nGetting events:")
        try:
            events = kubernetes_provider.query(
                command_type="get_events", namespace=namespace, pod_name=pod_name
            )
            print(json.dumps(events[:3], indent=2))  # Print first 3 events
        except Exception as e:
            print(f"Error: {e}")

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
        try:
            pods = kubernetes_provider.query(command_type="get_pods", namespace=namespace)
            print(f"Found {len(pods)} pods in namespace {namespace}")
        except Exception as e:
            print(f"Error: {e}")

    # Get namespaces
    print("\nGetting namespaces:")
    try:
        namespaces = kubernetes_provider.query(command_type="get_namespaces")
        print(f"Found {len(namespaces)} namespaces")
        for ns in namespaces[:3]:  # Show first 3
            print(f"  - {ns['metadata']['name']}")
    except Exception as e:
        print(f"Error: {e}")

    # Get services
    print("\nGetting services:")
    try:
        services = kubernetes_provider.query(command_type="get_services", namespace=namespace)
        print(f"Found {len(services)} services in namespace {namespace}")
        for svc in services[:3]:  # Show first 3
            print(f"  - {svc['metadata']['name']} ({svc['spec']['type']})")
    except Exception as e:
        print(f"Error: {e}")
