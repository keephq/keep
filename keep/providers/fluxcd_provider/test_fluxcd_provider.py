"""
Tests for the Flux CD provider.

This module contains unit tests for the Flux CD provider, which integrates with
Flux CD to pull topology data and alerts from a Kubernetes cluster.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from kubernetes.client.models.v1_event import V1Event
from kubernetes.client.models.v1_event_source import V1EventSource
from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_object_reference import V1ObjectReference

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.fluxcd_provider.fluxcd_provider import FluxcdProvider
from keep.providers.models.provider_config import ProviderConfig


class TestFluxcdProvider(unittest.TestCase):
    """
    Test the Flux CD provider.
    """

    def setUp(self):
        """
        Set up the test.
        """
        self.context_manager = ContextManager(tenant_id="test")
        self.provider_id = "test-provider"
        self.config = ProviderConfig(
            authentication={
                "kubeconfig": "",
                "context": "",
                "namespace": "flux-system",
            },
            name="Test Flux CD Provider",
        )
        self.provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )
        self.provider._initialize_kubernetes_client = MagicMock()
        self.provider._core_v1_api = MagicMock()
        self.provider._custom_objects_api = MagicMock()

    def test_validate_config(self):
        """
        Test the validate_config method.
        """
        self.provider.validate_config()
        self.assertEqual(self.provider.authentication_config.namespace, "flux-system")

    def test_validate_scopes(self):
        """
        Test the validate_scopes method.
        """
        self.provider._core_v1_api.list_namespace = MagicMock()
        scopes = self.provider.validate_scopes()
        self.assertEqual(scopes, {"authenticated": True})

    def test_event_to_alert(self):
        """
        Test the _event_to_alert method.
        """
        # Create a mock event
        event = V1Event(
            type="Warning",
            reason="GitOperationFailed",
            message="Failed to checkout and determine revision",
            involved_object=V1ObjectReference(
                kind="GitRepository",
                name="podinfo",
                namespace="default",
            ),
            metadata=V1ObjectMeta(
                name="podinfo.123456",
                namespace="default",
                annotations={"source.toolkit.fluxcd.io/revision": "main@sha1:123456"},
            ),
            source=V1EventSource(
                component="source-controller",
            ),
            first_timestamp="2023-08-22T20:24:06Z",
            last_timestamp="2023-08-22T20:24:18Z",
        )

        # Convert the event to an alert
        alert = self.provider._event_to_alert(event)

        # Check the alert
        self.assertEqual(alert.name, "GitRepository podinfo - GitOperationFailed")
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.HIGH)
        self.assertEqual(alert.environment, "default")
        self.assertEqual(alert.service, "podinfo")
        self.assertEqual(alert.source, ["fluxcd"])
        self.assertEqual(alert.labels["kind"], "GitRepository")
        self.assertEqual(alert.labels["namespace"], "default")
        self.assertEqual(alert.labels["name"], "podinfo")
        self.assertEqual(alert.labels["reason"], "GitOperationFailed")
        self.assertEqual(alert.labels["component"], "source-controller")
        self.assertEqual(alert.message, "Failed to checkout and determine revision")
        self.assertEqual(alert.description, "GitOperationFailed: Failed to checkout and determine revision")
        self.assertEqual(alert.fingerprint, "GitRepository-default-podinfo-GitOperationFailed")

    def test_get_alerts(self):
        """
        Test the get_alerts method.
        """
        # Create a mock event
        event = V1Event(
            type="Warning",
            reason="GitOperationFailed",
            message="Failed to checkout and determine revision",
            involved_object=V1ObjectReference(
                kind="GitRepository",
                name="podinfo",
                namespace="default",
            ),
            metadata=V1ObjectMeta(
                name="podinfo.123456",
                namespace="default",
                annotations={"source.toolkit.fluxcd.io/revision": "main@sha1:123456"},
            ),
            source=V1EventSource(
                component="source-controller",
            ),
            first_timestamp="2023-08-22T20:24:06Z",
            last_timestamp="2023-08-22T20:24:18Z",
            count=3,
        )

        # Mock the _get_flux_events method
        self.provider._get_flux_events = MagicMock(return_value=[event])

        # Create mock resources with non-ready status
        resources = {
            "gitrepositories": [
                {
                    "metadata": {
                        "name": "podinfo",
                        "namespace": "default",
                    },
                    "status": {
                        "conditions": [
                            {
                                "type": "Ready",
                                "status": "False",
                                "reason": "GitOperationFailed",
                                "message": "Failed to checkout and determine revision",
                            }
                        ]
                    }
                }
            ],
            "kustomizations": [],
            "helmrepositories": [],
            "helmreleases": [],
        }

        # Mock the _get_flux_resources method
        self.provider._get_flux_resources = MagicMock(return_value=resources)

        # Get the alerts
        alerts = self.provider.get_alerts()

        # Check the alerts
        self.assertEqual(len(alerts), 2)  # 1 from events, 1 from resource status

        # Find event alert
        event_alert = next((a for a in alerts if a.id == "gitrepository-podinfo-gitoperationfailed"), None)
        self.assertIsNotNone(event_alert)
        self.assertEqual(event_alert.name, "GitRepository podinfo - GitOperationFailed")
        self.assertEqual(event_alert.status, AlertStatus.FIRING)
        self.assertEqual(event_alert.severity, AlertSeverity.CRITICAL)  # Critical due to "failed" in reason
        self.assertEqual(event_alert.labels["count"], "3")

        # Find status alert
        status_alert = next((a for a in alerts if a.id == "gitrepository-podinfo-notready"), None)
        self.assertIsNotNone(status_alert)
        self.assertEqual(status_alert.name, "GitRepository podinfo is not ready")
        self.assertEqual(status_alert.status, AlertStatus.FIRING)
        self.assertEqual(status_alert.severity, AlertSeverity.HIGH)

    def test_get_alerts_with_error(self):
        """
        Test the get_alerts method with errors.
        """
        # Mock the _get_flux_events method to raise an exception
        self.provider._get_flux_events = MagicMock(side_effect=Exception("Test error"))

        # Mock the _get_flux_resources method to raise an exception
        self.provider._get_flux_resources = MagicMock(side_effect=Exception("Test error"))

        # Get the alerts - should not raise an exception
        alerts = self.provider.get_alerts()

        # Check the alerts - should be empty
        self.assertEqual(len(alerts), 0)

    def test_pull_topology(self):
        """
        Test the pull_topology method.
        """
        # Create mock resources
        resources = {
            "gitrepositories": [
                {
                    "kind": "GitRepository",
                    "metadata": {
                        "uid": "123",
                        "name": "podinfo",
                        "namespace": "default",
                        "labels": {"app": "podinfo"},
                        "annotations": {"description": "Podinfo repository"},
                    },
                    "spec": {
                        "url": "https://github.com/stefanprodan/podinfo",
                    },
                }
            ],
            "kustomizations": [
                {
                    "kind": "Kustomization",
                    "metadata": {
                        "uid": "456",
                        "name": "podinfo",
                        "namespace": "default",
                        "labels": {"app": "podinfo"},
                        "annotations": {"description": "Podinfo kustomization"},
                    },
                    "spec": {
                        "sourceRef": {
                            "kind": "GitRepository",
                            "name": "podinfo",
                        },
                    },
                }
            ],
            "helmrepositories": [
                {
                    "kind": "HelmRepository",
                    "metadata": {
                        "uid": "789",
                        "name": "bitnami",
                        "namespace": "default",
                        "labels": {"app": "bitnami"},
                        "annotations": {"description": "Bitnami Helm repository"},
                    },
                    "spec": {
                        "url": "https://charts.bitnami.com/bitnami",
                    },
                }
            ],
            "helmreleases": [
                {
                    "kind": "HelmRelease",
                    "metadata": {
                        "uid": "abc",
                        "name": "nginx",
                        "namespace": "default",
                        "labels": {"app": "nginx"},
                        "annotations": {"description": "Nginx Helm release"},
                    },
                    "spec": {
                        "chart": {
                            "spec": {
                                "sourceRef": {
                                    "kind": "HelmRepository",
                                    "name": "bitnami",
                                },
                            },
                        },
                    },
                }
            ],
        }

        # Mock the _get_flux_resources method
        self.provider._get_flux_resources = MagicMock(return_value=resources)

        # Pull the topology
        topology_services, applications = self.provider.pull_topology()

        # Check the topology
        self.assertEqual(len(topology_services), 4)

        # Find services by UID
        git_repo = next((s for s in topology_services if s.service == "123"), None)
        kustomization = next((s for s in topology_services if s.service == "456"), None)
        helm_repo = next((s for s in topology_services if s.service == "789"), None)
        helm_release = next((s for s in topology_services if s.service == "abc"), None)

        # Check GitRepository
        self.assertIsNotNone(git_repo)
        self.assertEqual(git_repo.display_name, "podinfo")
        self.assertEqual(git_repo.repository, "https://github.com/stefanprodan/podinfo")
        self.assertIn("git-repository", git_repo.tags)
        self.assertEqual(git_repo.category, "source")

        # Check Kustomization
        self.assertIsNotNone(kustomization)
        self.assertEqual(kustomization.display_name, "podinfo")
        self.assertIn("kustomization", kustomization.tags)
        self.assertEqual(kustomization.category, "deployment")

        # Check HelmRepository
        self.assertIsNotNone(helm_repo)
        self.assertEqual(helm_repo.display_name, "bitnami")
        self.assertEqual(helm_repo.repository, "https://charts.bitnami.com/bitnami")
        self.assertIn("helm-repository", helm_repo.tags)
        self.assertEqual(helm_repo.category, "source")

        # Check HelmRelease
        self.assertIsNotNone(helm_release)
        self.assertEqual(helm_release.display_name, "nginx")
        self.assertIn("helm-release", helm_release.tags)
        self.assertEqual(helm_release.category, "deployment")

        # Check applications
        self.assertEqual(applications, {})


    def test_get_provider_metadata(self):
        """
        Test the get_provider_metadata method.
        """
        # Mock the list_namespaced_deployment method
        deployment = MagicMock()
        deployment.metadata.name = "source-controller"
        container = MagicMock()
        container.name = "manager"
        container.image = "ghcr.io/fluxcd/source-controller:v1.0.0"
        deployment.spec.template.spec.containers = [container]

        deployments = MagicMock()
        deployments.items = [deployment]

        self.provider._core_v1_api.list_namespaced_deployment = MagicMock(return_value=deployments)

        # Mock the _get_flux_resources method
        resources = {
            "gitrepositories": [{"metadata": {"name": "repo1"}}, {"metadata": {"name": "repo2"}}],
            "kustomizations": [{"metadata": {"name": "kust1"}}],
            "helmrepositories": [{"metadata": {"name": "helm1"}}],
            "helmreleases": [{"metadata": {"name": "release1"}}, {"metadata": {"name": "release2"}}],
        }
        self.provider._get_flux_resources = MagicMock(return_value=resources)

        # Get the metadata
        metadata = self.provider.get_provider_metadata()

        # Check the metadata
        self.assertEqual(metadata["version"], "v1.0.0")
        self.assertEqual(metadata["controllers"], ["source-controller"])
        self.assertEqual(metadata["namespace"], "flux-system")
        self.assertEqual(metadata["resources"]["gitrepositories"], 2)
        self.assertEqual(metadata["resources"]["kustomizations"], 1)
        self.assertEqual(metadata["resources"]["helmrepositories"], 1)
        self.assertEqual(metadata["resources"]["helmreleases"], 2)

    def test_get_provider_metadata_with_error(self):
        """
        Test the get_provider_metadata method with errors.
        """
        # Mock the list_namespaced_deployment method to raise an exception
        self.provider._core_v1_api.list_namespaced_deployment = MagicMock(side_effect=Exception("Test error"))

        # Mock the _get_flux_resources method to raise an exception
        self.provider._get_flux_resources = MagicMock(side_effect=Exception("Test error"))

        # Get the metadata - should not raise an exception
        metadata = self.provider.get_provider_metadata()

        # Check the metadata - should have default values
        self.assertEqual(metadata["version"], "unknown")
        self.assertEqual(metadata["controllers"], [])
        self.assertEqual(metadata["namespace"], "flux-system")
        self.assertEqual(metadata["resources"], {})


if __name__ == "__main__":
    unittest.main()
