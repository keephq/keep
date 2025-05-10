"""
Flux CD Provider is a class that allows to get alerts and topology data from Flux CD.

Flux CD is a GitOps tool for Kubernetes that provides continuous delivery through
automated deployment, monitoring, and management of applications.

This provider integrates with Flux CD to:
1. Pull topology data from Flux CD resources (GitRepositories, Kustomizations, HelmReleases)
2. Get alerts from Flux CD events
3. Provide insights into the GitOps deployment process
"""

import dataclasses
import datetime
import json
import logging
import os
import tempfile
import uuid
from typing import Dict, List, Optional, Tuple, Any

import pydantic
import requests
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseTopologyProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class FluxcdProviderAuthConfig:
    """
    Flux CD authentication configuration.

    Supports multiple authentication methods:
    1. Kubeconfig file content (recommended for external access)
    2. In-cluster configuration (when running inside a Kubernetes cluster)
    3. Default kubeconfig file (from ~/.kube/config)
    """
    kubeconfig: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kubeconfig file content",
            "hint": "Kubeconfig file content for accessing the Kubernetes cluster where Flux CD is installed",
            "sensitive": True,
        },
        default="",
    )
    context: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kubernetes context to use",
            "hint": "The context from the kubeconfig to use",
        },
        default="",
    )
    namespace: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Namespace where Flux CD is installed",
            "hint": "Default is flux-system",
        },
        default="flux-system",
    )
    api_server: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kubernetes API server URL",
            "hint": "Only needed if not using kubeconfig",
            "validation": "any_http_url",
        },
        default=None,
    )
    token: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Kubernetes API token",
            "hint": "Only needed if not using kubeconfig",
            "sensitive": True,
        },
        default="",
    )
    insecure: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Skip TLS verification",
            "hint": "Only set to true in development environments",
            "type": "switch",
        },
        default=False,
    )


class FluxcdProvider(BaseTopologyProvider, ProviderHealthMixin):
    """Pull alerts and topology data from Flux CD."""

    PROVIDER_CATEGORY = ["Cloud Infrastructure"]
    PROVIDER_DISPLAY_NAME = "Flux CD"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Authenticated",
        ),
    ]
    FINGERPRINT_FIELDS = ["id", "name", "namespace"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._api_client = None
        self._core_v1_api = None
        self._custom_objects_api = None

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Flux CD provider.
        """
        self.logger.debug("Validating configuration for Flux CD provider")
        self.authentication_config = FluxcdProviderAuthConfig(
            **self.config.authentication
        )

    def _initialize_kubernetes_client(self):
        """
        Initialize the Kubernetes client.

        Supports multiple authentication methods:
        1. Kubeconfig file content
        2. API server URL and token
        3. In-cluster configuration
        4. Default kubeconfig file
        """
        if self._api_client is not None:
            return

        self.logger.debug("Initializing Kubernetes client")

        # Method 1: If kubeconfig is provided, use it
        if self.authentication_config.kubeconfig:
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp.write(self.authentication_config.kubeconfig.encode())
                temp_path = temp.name

            try:
                if self.authentication_config.context:
                    config.load_kube_config(
                        config_file=temp_path,
                        context=self.authentication_config.context
                    )
                else:
                    config.load_kube_config(config_file=temp_path)

                self._api_client = client.ApiClient()
                self._core_v1_api = client.CoreV1Api(self._api_client)
                self._custom_objects_api = client.CustomObjectsApi(self._api_client)

                self.logger.debug("Kubernetes client initialized with provided kubeconfig")
            except Exception as e:
                self.logger.error(f"Failed to initialize Kubernetes client with provided kubeconfig: {str(e)}")
                raise
            finally:
                os.unlink(temp_path)

        # Method 2: If API server and token are provided, use them
        elif self.authentication_config.api_server and self.authentication_config.token:
            try:
                # Create a configuration object
                configuration = client.Configuration()

                # Set the API server URL
                configuration.host = self.authentication_config.api_server

                # Set the token
                configuration.api_key = {"authorization": f"Bearer {self.authentication_config.token}"}

                # Set SSL verification
                configuration.verify_ssl = not self.authentication_config.insecure

                # Create the API client
                self._api_client = client.ApiClient(configuration)
                self._core_v1_api = client.CoreV1Api(self._api_client)
                self._custom_objects_api = client.CustomObjectsApi(self._api_client)

                self.logger.debug("Kubernetes client initialized with API server and token")
            except Exception as e:
                self.logger.error(f"Failed to initialize Kubernetes client with API server and token: {str(e)}")
                raise
        else:
            # Method 3: Try to use in-cluster config
            try:
                config.load_incluster_config()
                self._api_client = client.ApiClient()
                self._core_v1_api = client.CoreV1Api(self._api_client)
                self._custom_objects_api = client.CustomObjectsApi(self._api_client)

                self.logger.debug("Kubernetes client initialized with in-cluster config")
            except config.config_exception.ConfigException:
                # Method 4: Fall back to default kubeconfig
                try:
                    config.load_kube_config()
                    self._api_client = client.ApiClient()
                    self._core_v1_api = client.CoreV1Api(self._api_client)
                    self._custom_objects_api = client.CustomObjectsApi(self._api_client)

                    self.logger.debug("Kubernetes client initialized with default kubeconfig")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Kubernetes client: {str(e)}")
                    raise

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the scopes provided in the config are valid.
        """
        self.logger.info("Validating user scopes for Flux CD provider")
        authenticated = True
        try:
            self._initialize_kubernetes_client()
            # Try to list namespaces to check if authentication works
            self._core_v1_api.list_namespace()
        except Exception as e:
            self.logger.error(
                "Error while validating scope for Flux CD", extra={"exception": str(e)}
            )
            authenticated = str(e)
        return {
            "authenticated": authenticated,
        }

    def _get_flux_events(self, namespace: Optional[str] = None) -> List[Dict]:
        """
        Get Flux CD events from the Kubernetes API.

        Args:
            namespace: Optional namespace to filter events. If None, use the configured namespace.

        Returns:
            List of Flux CD events.
        """
        self._initialize_kubernetes_client()

        if namespace is None:
            namespace = self.authentication_config.namespace

        try:
            # Get all events in the namespace
            events = self._core_v1_api.list_namespaced_event(namespace)

            # Filter for events from Flux CD controllers
            flux_events = []
            for event in events.items:
                if (event.source and event.source.component and
                    (event.source.component.endswith("-controller") or
                     event.source.component == "notification-controller")):
                    flux_events.append(event)

            return flux_events
        except ApiException as e:
            self.logger.error(f"Error getting Flux CD events: {str(e)}")
            raise

    def _get_flux_resources(self, namespace: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        Get Flux CD resources from the Kubernetes API.

        Args:
            namespace: Optional namespace to filter resources. If None, use the configured namespace.

        Returns:
            Dictionary of Flux CD resources by kind.
        """
        self._initialize_kubernetes_client()

        if namespace is None:
            namespace = self.authentication_config.namespace

        resources = {}

        # Define the Flux CD API groups and kinds to fetch
        flux_resources = [
            # Source controller resources
            {"group": "source.toolkit.fluxcd.io", "version": "v1", "plural": "gitrepositories"},
            {"group": "source.toolkit.fluxcd.io", "version": "v1", "plural": "helmrepositories"},
            {"group": "source.toolkit.fluxcd.io", "version": "v1", "plural": "helmcharts"},
            {"group": "source.toolkit.fluxcd.io", "version": "v1beta2", "plural": "ocirepositories"},
            {"group": "source.toolkit.fluxcd.io", "version": "v1beta2", "plural": "buckets"},

            # Kustomize controller resources
            {"group": "kustomize.toolkit.fluxcd.io", "version": "v1", "plural": "kustomizations"},

            # Helm controller resources
            {"group": "helm.toolkit.fluxcd.io", "version": "v2", "plural": "helmreleases"},

            # Notification controller resources
            {"group": "notification.toolkit.fluxcd.io", "version": "v1", "plural": "receivers"},
            {"group": "notification.toolkit.fluxcd.io", "version": "v1beta3", "plural": "providers"},
            {"group": "notification.toolkit.fluxcd.io", "version": "v1beta3", "plural": "alerts"},
        ]

        try:
            for resource in flux_resources:
                try:
                    items = self._custom_objects_api.list_namespaced_custom_object(
                        group=resource["group"],
                        version=resource["version"],
                        namespace=namespace,
                        plural=resource["plural"],
                    )
                    resources[resource["plural"]] = items.get("items", [])
                except ApiException as e:
                    # Skip if the CRD is not installed
                    if e.status == 404:
                        self.logger.debug(f"CRD {resource['plural']} not found, skipping")
                        continue
                    else:
                        raise

            return resources
        except ApiException as e:
            self.logger.error(f"Error getting Flux CD resources: {str(e)}")
            raise

    def _event_to_alert(self, event) -> AlertDto:
        """
        Convert a Kubernetes event to a Keep alert.

        Args:
            event: Kubernetes event object.

        Returns:
            Keep alert DTO.
        """
        # Determine severity based on event type and reason
        severity = AlertSeverity.INFO
        if event.type == "Warning":
            severity = AlertSeverity.HIGH
            # Check for critical failures
            if any(critical in event.reason.lower() for critical in
                  ["failed", "error", "timeout", "backoff", "crash"]):
                severity = AlertSeverity.CRITICAL

        # Determine status based on event reason and count
        status = AlertStatus.FIRING
        if any(resolved in event.reason.lower() for resolved in
              ["succeeded", "complete", "resolved", "normal"]):
            status = AlertStatus.RESOLVED

        # Create a unique ID for the alert
        alert_id = f"{event.involved_object.kind.lower()}-{event.involved_object.name}-{event.reason.lower()}"

        # Extract metadata from annotations
        annotations = {}
        if event.metadata.annotations:
            annotations = event.metadata.annotations

        # Create the alert
        alert = AlertDto(
            id=alert_id,
            name=f"{event.involved_object.kind} {event.involved_object.name} - {event.reason}",
            status=status,
            severity=severity,
            lastReceived=event.last_timestamp.isoformat() if event.last_timestamp else datetime.datetime.now(datetime.timezone.utc).isoformat(),
            firingStartTime=event.first_timestamp.isoformat() if event.first_timestamp else None,
            environment=event.involved_object.namespace,
            service=event.involved_object.name,
            source=["fluxcd"],
            labels={
                "kind": event.involved_object.kind,
                "namespace": event.involved_object.namespace,
                "name": event.involved_object.name,
                "reason": event.reason,
                "component": event.source.component if event.source else "",
                "count": str(event.count) if hasattr(event, "count") else "1",
            },
            annotations=annotations,
            message=event.message,
            description=f"{event.reason}: {event.message}",
            fingerprint=f"{event.involved_object.kind}-{event.involved_object.namespace}-{event.involved_object.name}-{event.reason}",
        )

        return alert

    def _get_resource_status_alerts(self, resources) -> List[AlertDto]:
        """
        Generate alerts from Flux CD resource status.

        Args:
            resources: Dictionary of Flux CD resources.

        Returns:
            List of alerts.
        """
        alerts = []

        # Check GitRepository status
        for repo in resources.get("gitrepositories", []):
            if "status" in repo and "conditions" in repo["status"]:
                for condition in repo["status"]["conditions"]:
                    if condition["type"] == "Ready" and condition["status"] != "True":
                        # Create alert for non-ready repository
                        alert = AlertDto(
                            id=f"gitrepository-{repo['metadata']['name']}-notready",
                            name=f"GitRepository {repo['metadata']['name']} is not ready",
                            status=AlertStatus.FIRING,
                            severity=AlertSeverity.HIGH,
                            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            environment=repo["metadata"]["namespace"],
                            service=repo["metadata"]["name"],
                            source=["fluxcd"],
                            labels={
                                "kind": "GitRepository",
                                "namespace": repo["metadata"]["namespace"],
                                "name": repo["metadata"]["name"],
                                "reason": "NotReady",
                            },
                            message=condition.get("message", "Repository is not ready"),
                            description=f"GitRepository {repo['metadata']['name']} is not ready: {condition.get('message', 'No message')}",
                            fingerprint=f"GitRepository-{repo['metadata']['namespace']}-{repo['metadata']['name']}-NotReady",
                        )
                        alerts.append(alert)

        # Check Kustomization status
        for kust in resources.get("kustomizations", []):
            if "status" in kust and "conditions" in kust["status"]:
                for condition in kust["status"]["conditions"]:
                    if condition["type"] == "Ready" and condition["status"] != "True":
                        # Create alert for non-ready kustomization
                        alert = AlertDto(
                            id=f"kustomization-{kust['metadata']['name']}-notready",
                            name=f"Kustomization {kust['metadata']['name']} is not ready",
                            status=AlertStatus.FIRING,
                            severity=AlertSeverity.HIGH,
                            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            environment=kust["metadata"]["namespace"],
                            service=kust["metadata"]["name"],
                            source=["fluxcd"],
                            labels={
                                "kind": "Kustomization",
                                "namespace": kust["metadata"]["namespace"],
                                "name": kust["metadata"]["name"],
                                "reason": "NotReady",
                            },
                            message=condition.get("message", "Kustomization is not ready"),
                            description=f"Kustomization {kust['metadata']['name']} is not ready: {condition.get('message', 'No message')}",
                            fingerprint=f"Kustomization-{kust['metadata']['namespace']}-{kust['metadata']['name']}-NotReady",
                        )
                        alerts.append(alert)

        # Check HelmRelease status
        for release in resources.get("helmreleases", []):
            if "status" in release and "conditions" in release["status"]:
                for condition in release["status"]["conditions"]:
                    if condition["type"] == "Ready" and condition["status"] != "True":
                        # Create alert for non-ready helm release
                        alert = AlertDto(
                            id=f"helmrelease-{release['metadata']['name']}-notready",
                            name=f"HelmRelease {release['metadata']['name']} is not ready",
                            status=AlertStatus.FIRING,
                            severity=AlertSeverity.HIGH,
                            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            environment=release["metadata"]["namespace"],
                            service=release["metadata"]["name"],
                            source=["fluxcd"],
                            labels={
                                "kind": "HelmRelease",
                                "namespace": release["metadata"]["namespace"],
                                "name": release["metadata"]["name"],
                                "reason": "NotReady",
                            },
                            message=condition.get("message", "HelmRelease is not ready"),
                            description=f"HelmRelease {release['metadata']['name']} is not ready: {condition.get('message', 'No message')}",
                            fingerprint=f"HelmRelease-{release['metadata']['namespace']}-{release['metadata']['name']}-NotReady",
                        )
                        alerts.append(alert)

        return alerts

    def get_alerts(self, **kwargs) -> List[AlertDto]:
        """
        Get alerts from Flux CD.

        This method collects alerts from two sources:
        1. Kubernetes events related to Flux CD controllers
        2. Status conditions of Flux CD resources (GitRepositories, Kustomizations, HelmReleases)

        Returns:
            List of Keep alerts.
        """
        self.logger.info("Getting alerts from Flux CD")

        try:
            alerts = []

            # Get events from Flux CD
            try:
                events = self._get_flux_events()

                # Convert events to alerts
                for event in events:
                    # Only include Warning events as alerts
                    if event.type == "Warning":
                        alert = self._event_to_alert(event)
                        alerts.append(alert)

                self.logger.info(f"Found {len(alerts)} alerts from Flux CD events")
            except Exception as e:
                self.logger.error(f"Error getting alerts from Flux CD events: {str(e)}")
                # Continue with other alert sources

            # Get alerts from resource status
            try:
                resources = self._get_flux_resources()
                status_alerts = self._get_resource_status_alerts(resources)
                alerts.extend(status_alerts)

                self.logger.info(f"Found {len(status_alerts)} alerts from Flux CD resource status")
            except Exception as e:
                self.logger.error(f"Error getting alerts from Flux CD resource status: {str(e)}")
                # Continue with other alert sources

            self.logger.info(f"Found a total of {len(alerts)} alerts from Flux CD")
            return alerts
        except Exception as e:
            self.logger.error(f"Error getting alerts from Flux CD: {str(e)}")
            return []

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        """
        Pull topology data from Flux CD.

        Returns:
            Tuple containing:
            - List of topology services
            - Dictionary of applications to create (empty for now)
        """
        self.logger.info("Pulling topology from Flux CD")

        try:
            # Get resources from Flux CD
            resources = self._get_flux_resources()

            # Create topology services
            service_topology = {}

            # Process GitRepositories
            for repo in resources.get("gitrepositories", []):
                repo_uid = repo["metadata"]["uid"]
                service_topology[repo_uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=repo_uid,
                    display_name=repo["metadata"]["name"],
                    repository=repo["spec"].get("url", ""),
                    namespace=repo["metadata"]["namespace"],
                    tags=["git-repository", "flux-cd"],
                    category="source",
                    dependencies={},
                )

            # Process HelmRepositories
            for repo in resources.get("helmrepositories", []):
                repo_uid = repo["metadata"]["uid"]
                service_topology[repo_uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=repo_uid,
                    display_name=repo["metadata"]["name"],
                    repository=repo["spec"].get("url", ""),
                    namespace=repo["metadata"]["namespace"],
                    tags=["helm-repository", "flux-cd"],
                    category="source",
                    dependencies={},
                )

            # Process Kustomizations
            for kust in resources.get("kustomizations", []):
                kust_uid = kust["metadata"]["uid"]

                # Find the source reference
                dependencies = {}
                if "sourceRef" in kust["spec"]:
                    source_ref = kust["spec"]["sourceRef"]
                    # Find the source UID by name and kind
                    for repo in resources.get("gitrepositories", []):
                        if (repo["metadata"]["name"] == source_ref["name"] and
                            repo["kind"].lower() == source_ref["kind"].lower()):
                            dependencies[repo["metadata"]["uid"]] = "git"

                service_topology[kust_uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=kust_uid,
                    display_name=kust["metadata"]["name"],
                    namespace=kust["metadata"]["namespace"],
                    tags=["kustomization", "flux-cd"],
                    category="deployment",
                    dependencies=dependencies,
                )

            # Process HelmReleases
            for release in resources.get("helmreleases", []):
                release_uid = release["metadata"]["uid"]

                # Find the chart reference
                dependencies = {}
                if "chart" in release["spec"] and "spec" in release["spec"]["chart"]:
                    chart_ref = release["spec"]["chart"]["spec"].get("sourceRef")
                    if chart_ref:
                        # Find the source UID by name and kind
                        for repo in resources.get("helmrepositories", []):
                            if (repo["metadata"]["name"] == chart_ref["name"] and
                                repo["kind"].lower() == chart_ref["kind"].lower()):
                                dependencies[repo["metadata"]["uid"]] = "helm"

                service_topology[release_uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=release_uid,
                    display_name=release["metadata"]["name"],
                    namespace=release["metadata"]["namespace"],
                    tags=["helm-release", "flux-cd"],
                    category="deployment",
                    dependencies=dependencies,
                )

            self.logger.info(f"Found {len(service_topology)} services in Flux CD topology")
            return list(service_topology.values()), {}
        except Exception as e:
            self.logger.error(f"Error pulling topology from Flux CD: {str(e)}")
            return [], {}

    def get_provider_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the Flux CD installation.

        Returns:
            Dictionary of metadata including:
            - version: Flux CD version
            - controllers: List of installed Flux CD controllers
            - resources: Count of different Flux CD resources
            - namespace: Namespace where Flux CD is installed
        """
        self._initialize_kubernetes_client()

        metadata = {
            "version": "unknown",
            "controllers": [],
            "resources": {},
            "namespace": self.authentication_config.namespace,
        }

        try:
            # Get Flux CD deployments
            try:
                deployments = self._core_v1_api.list_namespaced_deployment(
                    namespace=self.authentication_config.namespace,
                    label_selector="app.kubernetes.io/part-of=flux"
                )

                if deployments.items:
                    # Get controllers and version
                    controllers = []
                    for deployment in deployments.items:
                        controllers.append(deployment.metadata.name)

                        # Try to get version from source-controller
                        if deployment.metadata.name == "source-controller":
                            for container in deployment.spec.template.spec.containers:
                                if container.name == "manager":
                                    # Extract version from image tag
                                    image = container.image
                                    if ":" in image:
                                        metadata["version"] = image.split(":")[-1]

                    metadata["controllers"] = controllers
            except Exception as e:
                self.logger.error(f"Error getting Flux CD deployments: {str(e)}")

            # Get resource counts
            try:
                resources = self._get_flux_resources()
                resource_counts = {}

                for resource_type, items in resources.items():
                    resource_counts[resource_type] = len(items)

                metadata["resources"] = resource_counts
            except Exception as e:
                self.logger.error(f"Error getting Flux CD resource counts: {str(e)}")

            return metadata
        except Exception as e:
            self.logger.error(f"Error getting Flux CD metadata: {str(e)}")
            return metadata
