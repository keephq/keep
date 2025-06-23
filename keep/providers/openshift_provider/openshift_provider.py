import dataclasses
import datetime
import json
import traceback

import openshift_client as oc
import pydantic
import requests
import warnings
from kubernetes import client
from kubernetes.client.rest import ApiException
from openshift_client import Context, OpenShiftPythonException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class OpenshiftProviderAuthConfig:
    """Openshift authentication configuration."""

    api_server: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "name": "api_server",
            "description": "The openshift api server url",
            "required": True,
            "sensitive": False,
            "validation": "any_http_url",
        },
    )
    token: str = dataclasses.field(
        metadata={
            "name": "token",
            "description": "The openshift token",
            "required": True,
            "sensitive": True,
        },
    )
    insecure: bool = dataclasses.field(
        default=False,
        metadata={
            "name": "insecure",
            "description": "Skip TLS verification",
            "required": False,
            "sensitive": False,
            "type": "switch",
        },
    )


class OpenshiftProvider(BaseProvider):
    """Perform rollout restart actions and query resources on Openshift."""

    provider_id: str
    PROVIDER_DISPLAY_NAME = "Openshift"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect_to_openshift",
            description="Check if the provided token can connect to the openshift server",
            mandatory=True,
            alias="Connect to the openshift",
        )
    ]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.authentication_config = None
        self._k8s_client = None
        self.validate_config()

    def dispose(self):
        """Dispose the provider."""
        if self._k8s_client:
            self._k8s_client.api_client.rest_client.pool_manager.clear()

    def validate_config(self):
        """
        Validates required configuration for Openshift provider.
        """

        if self.config.authentication is None:
            self.config.authentication = {}
        self.authentication_config = OpenshiftProviderAuthConfig(
            **self.config.authentication
        )

    def __get_ocp_client(self):
        """Get the Openshift client."""
        oc_context = Context()
        oc_context.api_server = self.authentication_config.api_server
        oc_context.token = self.authentication_config.token
        oc_context.insecure = self.authentication_config.insecure
        return oc_context

    def __get_k8s_client(self):
        """Get the Kubernetes client for OpenShift API access."""
        if self._k8s_client is None:
            client_configuration = client.Configuration()
            client_configuration.host = self.authentication_config.api_server
            client_configuration.verify_ssl = not self.authentication_config.insecure
            client_configuration.api_key = {
                "authorization": "Bearer " + self.authentication_config.token
            }
            self._k8s_client = client.ApiClient(client_configuration)
        return self._k8s_client

    def __test_connection_via_rest_api(self):
        """
        Test connection to OpenShift using REST API instead of CLI.
        This is more reliable as it doesn't depend on oc CLI being installed.
        """
        try:
            # Suppress SSL warnings if insecure is True
            if self.authentication_config.insecure:
                # Suppress SSL verification warnings
                warnings.filterwarnings('ignore', message='Unverified HTTPS request')
            
            # Test API connectivity by hitting the /version endpoint
            headers = {
                'Authorization': f'Bearer {self.authentication_config.token}',
                'Accept': 'application/json'
            }
            
            verify_ssl = not self.authentication_config.insecure
            
            # Try to get cluster version info
            response = requests.get(
                f"{self.authentication_config.api_server}/version",
                headers=headers,
                verify=verify_ssl,
                timeout=30
            )
            
            if response.status_code == 200:
                self.logger.info("Successfully connected to OpenShift cluster via REST API")
                return True, None
            else:
                error_msg = f"API returned status code {response.status_code}: {response.text}"
                self.logger.error(f"Failed to connect to OpenShift cluster: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error: {str(e)}"
            self.logger.error(f"Failed to connect to OpenShift cluster: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"Failed to connect to OpenShift cluster: {error_msg}")
            return False, error_msg

    def validate_scopes(self):
        """
        Validates that the provided token has the required scopes to use the provider.
        Uses REST API validation instead of CLI commands for better reliability.
        """
        self.logger.info("Validating scopes for OpenShift provider")
        
        try:
            # Try REST API approach first
            success, error_msg = self.__test_connection_via_rest_api()
            
            if success:
                self.logger.info("Successfully validated OpenShift connection")
                scopes = {
                    "connect_to_openshift": True,
                }
            else:
                self.logger.error(f"OpenShift validation failed: {error_msg}")
                scopes = {
                    "connect_to_openshift": error_msg,
                }
                
        except Exception as e:
            self.logger.exception("Error validating scopes for OpenShift provider")
            scopes = {
                "connect_to_openshift": str(e),
            }
            
        return scopes

    def _query(self, command_type: str, **kwargs):
        """
        Query OpenShift resources.
        Args:
            command_type (str): The type of query to perform. Supported queries are:
                - get_logs: Get logs from a pod  
                - get_events: Get events for a namespace or pod
                - get_pods: List pods in a namespace or across all namespaces
                - get_node_pressure: Get node pressure conditions
                - get_pvc: List persistent volume claims
                - get_routes: List OpenShift routes
                - get_deploymentconfigs: List OpenShift deployment configs
                - get_projects: List OpenShift projects
            **kwargs: Additional arguments for the query.
        """
        k8s_client = self.__get_k8s_client()

        if command_type == "get_logs":
            return self.__get_logs(k8s_client, **kwargs)
        elif command_type == "get_events":
            return self.__get_events(k8s_client, **kwargs)
        elif command_type == "get_pods":
            return self.__get_pods(k8s_client, **kwargs)
        elif command_type == "get_node_pressure":
            return self.__get_node_pressure(k8s_client, **kwargs)
        elif command_type == "get_pvc":
            return self.__get_pvc(k8s_client, **kwargs)
        elif command_type == "get_routes":
            return self.__get_routes(**kwargs)
        elif command_type == "get_deploymentconfigs":
            return self.__get_deploymentconfigs(**kwargs)
        elif command_type == "get_projects":
            return self.__get_projects(**kwargs)
        else:
            raise NotImplementedError(f"Command type {command_type} is not implemented")

    def _notify(self, action: str, **kwargs):
        """
        Perform actions on OpenShift resources.
        Args:
            action (str): The action to perform. Supported actions are:
                - rollout_restart: Restart a deployment, statefulset, or daemonset
                - restart_pod: Restart a pod by deleting it
                - scale_deployment: Scale a deployment to specified replicas
                - scale_deploymentconfig: Scale a deployment config to specified replicas
            **kwargs: Additional arguments for the action.
        """
        if action == "rollout_restart":
            return self.__rollout_restart(**kwargs)
        elif action == "restart_pod":
            return self.__restart_pod(**kwargs)
        elif action == "scale_deployment":
            return self.__scale_deployment(**kwargs)
        elif action == "scale_deploymentconfig":
            return self.__scale_deploymentconfig(**kwargs)
        else:
            raise NotImplementedError(f"Action {action} is not implemented")

    def __get_logs(self, k8s_client, namespace, pod_name, container_name=None, tail_lines=100, **kwargs):
        """Get logs from a pod."""
        self.logger.info(f"Getting logs for pod {pod_name} in namespace {namespace}")
        core_v1 = client.CoreV1Api(k8s_client)

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

    def __get_events(self, k8s_client, namespace, pod_name=None, sort_by=None, **kwargs):
        """Get events for a namespace or specific pod."""
        self.logger.info(
            f"Getting events in namespace {namespace}"
            + (f" for pod {pod_name}" if pod_name else ""),
        )

        core_v1 = client.CoreV1Api(k8s_client)

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
                self.logger.info(f"Sorting events by {sort_by}")
                try:
                    sorted_events = sorted(
                        events.items,
                        key=lambda event: getattr(event, sort_by, None),
                        reverse=True,
                    )
                    return sorted_events
                except Exception:
                    self.logger.exception(f"Error sorting events by {sort_by}")

            # Convert events to dict
            return [event.to_dict() for event in events.items]
        except ApiException as e:
            self.logger.exception("Error getting events")
            raise Exception(f"Error getting events: {e}") from e

    def __get_pods(self, k8s_client, namespace=None, label_selector=None, **kwargs):
        """List pods in a namespace or across all namespaces."""
        core_v1 = client.CoreV1Api(k8s_client)

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

    def __get_node_pressure(self, k8s_client, **kwargs):
        """Get node pressure conditions (Memory, Disk, PID)."""
        self.logger.info("Getting node pressure conditions")
        core_v1 = client.CoreV1Api(k8s_client)

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

    def __get_pvc(self, k8s_client, namespace=None, **kwargs):
        """List persistent volume claims in a namespace or across all namespaces."""
        core_v1 = client.CoreV1Api(k8s_client)

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

    def __get_routes(self, namespace=None, **kwargs):
        """List OpenShift routes."""
        self.logger.info("Getting OpenShift routes")
        
        try:
            # Use REST API to get routes
            headers = {
                'Authorization': f'Bearer {self.authentication_config.token}',
                'Accept': 'application/json'
            }
            
            verify_ssl = not self.authentication_config.insecure
            
            if namespace:
                url = f"{self.authentication_config.api_server}/apis/route.openshift.io/v1/namespaces/{namespace}/routes"
            else:
                url = f"{self.authentication_config.api_server}/apis/route.openshift.io/v1/routes"
            
            response = requests.get(url, headers=headers, verify=verify_ssl, timeout=30)
            response.raise_for_status()
            
            routes_data = response.json()
            return routes_data.get('items', [])
            
        except Exception as e:
            self.logger.error(f"Error getting routes: {e}")
            raise Exception(f"Error getting routes: {e}")

    def __get_deploymentconfigs(self, namespace=None, **kwargs):
        """List OpenShift deployment configs."""
        self.logger.info("Getting OpenShift deployment configs")
        
        try:
            # Use REST API to get deployment configs
            headers = {
                'Authorization': f'Bearer {self.authentication_config.token}',
                'Accept': 'application/json'
            }
            
            verify_ssl = not self.authentication_config.insecure
            
            if namespace:
                url = f"{self.authentication_config.api_server}/apis/apps.openshift.io/v1/namespaces/{namespace}/deploymentconfigs"
            else:
                url = f"{self.authentication_config.api_server}/apis/apps.openshift.io/v1/deploymentconfigs"
            
            response = requests.get(url, headers=headers, verify=verify_ssl, timeout=30)
            response.raise_for_status()
            
            dc_data = response.json()
            return dc_data.get('items', [])
            
        except Exception as e:
            self.logger.error(f"Error getting deployment configs: {e}")
            raise Exception(f"Error getting deployment configs: {e}")

    def __get_projects(self, **kwargs):
        """List OpenShift projects."""
        self.logger.info("Getting OpenShift projects")
        
        try:
            # Use REST API to get projects
            headers = {
                'Authorization': f'Bearer {self.authentication_config.token}',
                'Accept': 'application/json'
            }
            
            verify_ssl = not self.authentication_config.insecure
            url = f"{self.authentication_config.api_server}/apis/project.openshift.io/v1/projects"
            
            response = requests.get(url, headers=headers, verify=verify_ssl, timeout=30)
            response.raise_for_status()
            
            projects_data = response.json()
            return projects_data.get('items', [])
            
        except Exception as e:
            self.logger.error(f"Error getting projects: {e}")
            raise Exception(f"Error getting projects: {e}")

    def __rollout_restart(self, kind, name, namespace, labels=None, **kwargs):
        """Perform a rollout restart on a deployment, statefulset, or daemonset using REST API."""
        self.logger.info(f"Performing rollout restart for {kind} {name} in namespace {namespace}")

        k8s_client = self.__get_k8s_client()
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

        apps_v1 = client.AppsV1Api(k8s_client)
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
            elif kind.lower() == "deploymentconfig":
                # Handle OpenShift DeploymentConfig using REST API
                return self.__rollout_restart_deploymentconfig(name, namespace)
            else:
                raise ValueError(f"Unsupported kind {kind} to perform rollout restart")
        except ApiException as e:
            self.logger.error(f"Error performing rollout restart for {kind} {name}: {e}")
            raise Exception(f"Error performing rollout restart for {kind} {name}: {e}")

        self.logger.info(f"Successfully performed rollout restart for {kind} {name}")
        return {
            "status": "success",
            "message": f"Successfully performed rollout restart for {kind} {name}",
        }

    def __rollout_restart_deploymentconfig(self, name, namespace):
        """Restart a DeploymentConfig using OpenShift REST API."""
        try:
            headers = {
                'Authorization': f'Bearer {self.authentication_config.token}',
                'Content-Type': 'application/json'
            }
            
            verify_ssl = not self.authentication_config.insecure
            url = f"{self.authentication_config.api_server}/apis/apps.openshift.io/v1/namespaces/{namespace}/deploymentconfigs/{name}/instantiate"
            
            # Trigger a new deployment
            body = {
                "kind": "DeploymentRequest",
                "apiVersion": "apps.openshift.io/v1",
                "name": name,
                "latest": True,
                "force": True
            }
            
            response = requests.post(url, headers=headers, json=body, verify=verify_ssl, timeout=30)
            response.raise_for_status()
            
            self.logger.info(f"Successfully restarted DeploymentConfig {name}")
            return {
                "status": "success",
                "message": f"Successfully restarted DeploymentConfig {name}",
            }
            
        except Exception as e:
            self.logger.error(f"Error restarting DeploymentConfig {name}: {e}")
            raise Exception(f"Error restarting DeploymentConfig {name}: {e}")

    def __restart_pod(self, namespace, pod_name, container_name=None, message=None, **kwargs):
        """Restart a pod by deleting it (it will be recreated by its controller)."""
        k8s_client = self.__get_k8s_client()
        core_v1 = client.CoreV1Api(k8s_client)

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

    def __scale_deployment(self, namespace, deployment_name, replicas, **kwargs):
        """Scale a deployment to specified replicas."""
        k8s_client = self.__get_k8s_client()
        apps_v1 = client.AppsV1Api(k8s_client)
        
        self.logger.info(f"Scaling deployment {deployment_name} in namespace {namespace} to {replicas} replicas")
        
        try:
            apps_v1.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
            
            return {
                "status": "success",
                "message": f"Successfully scaled deployment {deployment_name} to {replicas} replicas",
            }
        except ApiException as e:
            error_message = f"Error scaling deployment {deployment_name}: {e}"
            self.logger.error(error_message)
            raise Exception(error_message)

    def __scale_deploymentconfig(self, namespace, deploymentconfig_name, replicas, **kwargs):
        """Scale a DeploymentConfig to specified replicas using OpenShift REST API."""
        try:
            headers = {
                'Authorization': f'Bearer {self.authentication_config.token}',
                'Content-Type': 'application/strategic-merge-patch+json'
            }
            
            verify_ssl = not self.authentication_config.insecure
            url = f"{self.authentication_config.api_server}/apis/apps.openshift.io/v1/namespaces/{namespace}/deploymentconfigs/{deploymentconfig_name}/scale"
            
            body = {
                "spec": {
                    "replicas": replicas
                }
            }
            
            response = requests.patch(url, headers=headers, json=body, verify=verify_ssl, timeout=30)
            response.raise_for_status()
            
            self.logger.info(f"Successfully scaled DeploymentConfig {deploymentconfig_name} to {replicas} replicas")
            return {
                "status": "success",
                "message": f"Successfully scaled DeploymentConfig {deploymentconfig_name} to {replicas} replicas",
            }
            
        except Exception as e:
            self.logger.error(f"Error scaling DeploymentConfig {deploymentconfig_name}: {e}")
            raise Exception(f"Error scaling DeploymentConfig {deploymentconfig_name}: {e}")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    url = os.environ.get("OPENSHIFT_URL")
    token = os.environ.get("OPENSHIFT_TOKEN")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "api_server": url,
            "token": token,
        }
    )
    openshift_provider = OpenshiftProvider(context_manager, "openshift-keephq", config)

    # Test validation
    scopes = openshift_provider.validate_scopes()
    print("Validation result:", scopes)
    
    # Test query operations
    try:
        projects = openshift_provider.query(command_type="get_projects")
        print(f"Found {len(projects)} projects")
    except Exception as e:
        print(f"Error getting projects: {e}")
        
    # Test restart action
    try:
        restart = openshift_provider.notify(action="rollout_restart", kind="deployment", name="nginx", namespace="default")
        print(restart)
    except Exception as e:
        print(f"Error restarting: {e}")
