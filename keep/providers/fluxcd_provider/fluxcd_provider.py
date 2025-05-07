"""
FluxCD Provider is a class that allows to get Flux CD resources and map them to keep services and applications.
"""

import dataclasses
import os
import tempfile

import pydantic
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config import kube_config

from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseTopologyProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class FluxcdProviderAuthConfig:
    """
    FluxCD authentication configuration.
    """

    kubeconfig: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Kubeconfig file content",
            "hint": "Content of the kubeconfig file",
            "sensitive": True,
        },
    )
    context: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Kubernetes context to use",
            "hint": "Context name from the kubeconfig file",
        },
    )
    namespace: str = dataclasses.field(
        default="flux-system",
        metadata={
            "required": False,
            "description": "Namespace where Flux CD is installed",
            "hint": "Default is flux-system",
        },
    )
    api_server: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Kubernetes API server URL",
            "hint": "Example: https://kubernetes.example.com",
        },
    )
    token: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Kubernetes API token",
            "hint": "Service account token with permissions to access Flux CD resources",
            "sensitive": True,
        },
    )
    insecure: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Skip TLS verification",
            "hint": "Set to true to skip TLS verification",
        },
    )


class FluxcdProvider(BaseTopologyProvider):
    """Get topology and alerts from Flux CD."""

    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    PROVIDER_DISPLAY_NAME = "Flux CD"

    PROVIDER_TAGS = ["gitops", "kubernetes", "topology"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Authenticated",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._k8s_client = None

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for FluxCD provider.
        """
        self.logger.debug("Validating configuration for FluxCD provider")
        auth_config = self.config.authentication or {}
        self.authentication_config = FluxcdProviderAuthConfig(
            **auth_config
        )

    @property
    def k8s_client(self):
        """
        Get or create a Kubernetes client.
        """
        if self._k8s_client:
            return self._k8s_client

        try:
            # Try to load from kubeconfig content
            if self.authentication_config.kubeconfig:
                self.logger.debug("Loading Kubernetes client from kubeconfig content")
                # Create a temporary file with the kubeconfig content
                with tempfile.NamedTemporaryFile(delete=False) as temp:
                    temp.write(self.authentication_config.kubeconfig.encode())
                    temp_path = temp.name

                try:
                    # Load the kubeconfig from the temporary file
                    kube_config.load_kube_config(
                        config_file=temp_path,
                        context=self.authentication_config.context,
                    )
                    self._k8s_client = client.CustomObjectsApi()
                finally:
                    # Clean up the temporary file
                    os.unlink(temp_path)

            # Try to load from API server and token
            elif self.authentication_config.api_server and self.authentication_config.token:
                self.logger.debug("Loading Kubernetes client from API server and token")
                configuration = client.Configuration()
                configuration.host = self.authentication_config.api_server
                configuration.api_key = {"authorization": f"Bearer {self.authentication_config.token}"}
                configuration.verify_ssl = not self.authentication_config.insecure
                client.Configuration.set_default(configuration)
                self._k8s_client = client.CustomObjectsApi()

            # Try to load from in-cluster configuration
            else:
                self.logger.debug("Loading Kubernetes client from in-cluster configuration")
                config.load_incluster_config()
                self._k8s_client = client.CustomObjectsApi()

            return self._k8s_client

        except Exception as e:
            self.logger.error(
                "Error initializing Kubernetes client", extra={"exception": str(e)}
            )
            raise

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating user scopes for FluxCD provider")
        authenticated = True
        try:
            # Try to list GitRepositories to validate authentication
            self.__list_git_repositories()
        except Exception as e:
            self.logger.error(
                "Error while validating scope for FluxCD", extra={"exception": str(e)}
            )
            authenticated = str(e)
        return {
            "authenticated": authenticated,
        }

    def __list_git_repositories(self):
        """
        List GitRepository resources from Flux CD.
        """
        self.logger.info("Listing GitRepository resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.authentication_config.namespace,
                plural="gitrepositories",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing GitRepository resources",
                extra={"exception": str(e)},
            )
            raise

    def __list_helm_repositories(self):
        """
        List HelmRepository resources from Flux CD.
        """
        self.logger.info("Listing HelmRepository resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.authentication_config.namespace,
                plural="helmrepositories",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing HelmRepository resources",
                extra={"exception": str(e)},
            )
            raise

    def __list_helm_charts(self):
        """
        List HelmChart resources from Flux CD.
        """
        self.logger.info("Listing HelmChart resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.authentication_config.namespace,
                plural="helmcharts",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing HelmChart resources",
                extra={"exception": str(e)},
            )
            raise

    def __list_oci_repositories(self):
        """
        List OCIRepository resources from Flux CD.
        """
        self.logger.info("Listing OCIRepository resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.authentication_config.namespace,
                plural="ocirepositories",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing OCIRepository resources",
                extra={"exception": str(e)},
            )
            raise

    def __list_buckets(self):
        """
        List Bucket resources from Flux CD.
        """
        self.logger.info("Listing Bucket resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="source.toolkit.fluxcd.io",
                version="v1",
                namespace=self.authentication_config.namespace,
                plural="buckets",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing Bucket resources",
                extra={"exception": str(e)},
            )
            raise

    def __list_kustomizations(self):
        """
        List Kustomization resources from Flux CD.
        """
        self.logger.info("Listing Kustomization resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="kustomize.toolkit.fluxcd.io",
                version="v1",
                namespace=self.authentication_config.namespace,
                plural="kustomizations",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing Kustomization resources",
                extra={"exception": str(e)},
            )
            raise

    def __list_helm_releases(self):
        """
        List HelmRelease resources from Flux CD.
        """
        self.logger.info("Listing HelmRelease resources from Flux CD")
        try:
            return self.k8s_client.list_namespaced_custom_object(
                group="helm.toolkit.fluxcd.io",
                version="v2",
                namespace=self.authentication_config.namespace,
                plural="helmreleases",
            )
        except ApiException as e:
            self.logger.error(
                "Error listing HelmRelease resources",
                extra={"exception": str(e)},
            )
            raise

    def __get_resource_events(self, resource_name, resource_kind):
        """
        Get events for a specific resource.
        """
        self.logger.info(f"Getting events for {resource_kind}/{resource_name}")
        try:
            field_selector = f"involvedObject.name={resource_name},involvedObject.kind={resource_kind}"
            events = client.CoreV1Api().list_namespaced_event(
                namespace=self.authentication_config.namespace,
                field_selector=field_selector,
            )
            return events.items
        except ApiException as e:
            self.logger.error(
                f"Error getting events for {resource_kind}/{resource_name}",
                extra={"exception": str(e)},
            )
            return []

    def __get_repository_url(self, resource):
        """
        Extract repository URL from a resource.
        """
        if resource["kind"] == "GitRepository":
            return resource["spec"].get("url")
        elif resource["kind"] == "HelmRepository":
            return resource["spec"].get("url")
        elif resource["kind"] == "OCIRepository":
            return resource["spec"].get("url")
        elif resource["kind"] == "Bucket":
            endpoint = resource["spec"].get("endpoint")
            bucket = resource["spec"].get("bucketName")
            if endpoint and bucket:
                return f"{endpoint}/{bucket}"
        return None

    def __get_alerts_from_resource(self, resource, resource_kind):
        """
        Get alerts from a resource's status and events.
        """
        alerts = []
        name = resource["metadata"]["name"]
        uid = resource["metadata"]["uid"]

        # Check resource status conditions
        conditions = resource.get("status", {}).get("conditions", [])
        for condition in conditions:
            if condition.get("status") != "True" and condition.get("type") != "Ready":
                alert = {
                    "id": f"{uid}-{condition.get('type')}",
                    "name": f"{resource_kind} {name} - {condition.get('type')}",
                    "description": condition.get("message", "Resource not ready"),
                    "status": "firing",
                    "severity": "critical" if condition.get("type") == "Ready" else "high",
                    "source": f"fluxcd-{resource_kind.lower()}",
                    "resource": {
                        "name": name,
                        "kind": resource_kind,
                        "namespace": resource["metadata"]["namespace"],
                    },
                    "timestamp": condition.get("lastTransitionTime"),
                }
                alerts.append(alert)

        # Get events for this resource
        events = self.__get_resource_events(name, resource_kind)
        for event in events:
            # Skip normal events
            if event.type == "Normal":
                continue

            # Create alert from warning event
            alert = {
                "id": event.metadata.uid,
                "name": f"{resource_kind} {name} - {event.reason}",
                "description": event.message,
                "status": "firing",
                "severity": "critical" if any(x in event.reason.lower() for x in ["failed", "error", "timeout", "backoff", "crash"]) else "high",
                "source": f"fluxcd-{resource_kind.lower()}-event",
                "resource": {
                    "name": name,
                    "kind": resource_kind,
                    "namespace": resource["metadata"]["namespace"],
                },
                "timestamp": event.last_timestamp,
            }
            alerts.append(alert)

        return alerts

    def _get_alerts(self):
        """
        Get alerts from Flux CD resources.
        """
        self.logger.info("Getting alerts from Flux CD")
        alerts = []

        try:
            # Get all resources
            git_repositories = self.__list_git_repositories().get("items", [])
            helm_repositories = self.__list_helm_repositories().get("items", [])
            helm_charts = self.__list_helm_charts().get("items", [])
            oci_repositories = self.__list_oci_repositories().get("items", [])
            buckets = self.__list_buckets().get("items", [])
            kustomizations = self.__list_kustomizations().get("items", [])
            helm_releases = self.__list_helm_releases().get("items", [])

            # Get alerts from all resources
            for resource in git_repositories:
                alerts.extend(self.__get_alerts_from_resource(resource, "GitRepository"))

            for resource in helm_repositories:
                alerts.extend(self.__get_alerts_from_resource(resource, "HelmRepository"))

            for resource in helm_charts:
                alerts.extend(self.__get_alerts_from_resource(resource, "HelmChart"))

            for resource in oci_repositories:
                alerts.extend(self.__get_alerts_from_resource(resource, "OCIRepository"))

            for resource in buckets:
                alerts.extend(self.__get_alerts_from_resource(resource, "Bucket"))

            for resource in kustomizations:
                alerts.extend(self.__get_alerts_from_resource(resource, "Kustomization"))

            for resource in helm_releases:
                alerts.extend(self.__get_alerts_from_resource(resource, "HelmRelease"))

        except Exception as e:
            self.logger.error(
                "Error getting alerts from Flux CD", extra={"exception": str(e)}
            )

        return alerts

    def pull_topology(self):
        """
        Pull topology information from Flux CD.
        """
        self.logger.info("Pulling topology from Flux CD")
        service_topology = {}

        try:
            # Get all source resources
            git_repositories = self.__list_git_repositories().get("items", [])
            helm_repositories = self.__list_helm_repositories().get("items", [])
            helm_charts = self.__list_helm_charts().get("items", [])
            oci_repositories = self.__list_oci_repositories().get("items", [])
            buckets = self.__list_buckets().get("items", [])

            # Get all deployment resources
            kustomizations = self.__list_kustomizations().get("items", [])
            helm_releases = self.__list_helm_releases().get("items", [])

            # Process source resources
            for repo in git_repositories + helm_repositories + oci_repositories + buckets:
                uid = repo["metadata"]["uid"]
                name = repo["metadata"]["name"]
                kind = repo["kind"]

                service_topology[uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=uid,
                    display_name=f"{kind}/{name}",
                    repository=self.__get_repository_url(repo),
                )

            # Process HelmCharts (they depend on HelmRepositories)
            for chart in helm_charts:
                uid = chart["metadata"]["uid"]
                name = chart["metadata"]["name"]

                # Find the source repository
                source_ref = chart["spec"].get("sourceRef", {})
                source_kind = source_ref.get("kind")
                source_name = source_ref.get("name")

                service_topology[uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=uid,
                    display_name=f"HelmChart/{name}",
                )

                # Add dependency to source repository
                if source_kind and source_name:
                    for repo in git_repositories + helm_repositories + oci_repositories + buckets:
                        if repo["kind"] == source_kind and repo["metadata"]["name"] == source_name:
                            service_topology[uid].dependencies[repo["metadata"]["uid"]] = "source"
                            break

            # Process Kustomizations
            for kustomization in kustomizations:
                uid = kustomization["metadata"]["uid"]
                name = kustomization["metadata"]["name"]

                service_topology[uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=uid,
                    display_name=f"Kustomization/{name}",
                )

                # Find the source repository
                source_ref = kustomization["spec"].get("sourceRef", {})
                source_kind = source_ref.get("kind")
                source_name = source_ref.get("name")

                # Add dependency to source repository
                if source_kind and source_name:
                    for repo in git_repositories + helm_repositories + oci_repositories + buckets:
                        if repo["kind"] == source_kind and repo["metadata"]["name"] == source_name:
                            service_topology[uid].dependencies[repo["metadata"]["uid"]] = "source"
                            break

            # Process HelmReleases
            for release in helm_releases:
                uid = release["metadata"]["uid"]
                name = release["metadata"]["name"]

                service_topology[uid] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=uid,
                    display_name=f"HelmRelease/{name}",
                )

                # Find the chart source
                chart_spec = release["spec"].get("chart", {})
                spec = chart_spec.get("spec", {})
                source_ref = spec.get("sourceRef", {})
                source_kind = source_ref.get("kind")
                source_name = source_ref.get("name")

                # Add dependency to source repository or chart
                if source_kind and source_name:
                    for repo in git_repositories + helm_repositories + oci_repositories + buckets:
                        if repo["kind"] == source_kind and repo["metadata"]["name"] == source_name:
                            service_topology[uid].dependencies[repo["metadata"]["uid"]] = "source"
                            break

                    # Check if it depends on a HelmChart
                    for chart in helm_charts:
                        if chart["metadata"]["name"] == spec.get("chart") and chart["spec"].get("sourceRef", {}).get("name") == source_name:
                            service_topology[uid].dependencies[chart["metadata"]["uid"]] = "chart"
                            break

            return list(service_topology.values()), {}

        except Exception as e:
            self.logger.error(
                "Error pulling topology from Flux CD", extra={"exception": str(e)}
            )
            return [], {}
