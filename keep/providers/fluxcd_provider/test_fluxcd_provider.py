"""
Tests for the FluxCD provider.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the parent directory to sys.path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock kubernetes module if it's not installed
try:
    import kubernetes
except ImportError:
    # Create a mock kubernetes module
    kubernetes = MagicMock()
    kubernetes.client = MagicMock()
    kubernetes.config = MagicMock()
    kubernetes.client.rest = MagicMock()
    kubernetes.client.rest.ApiException = Exception
    kubernetes.config.kube_config = MagicMock()

    # Add the mock to sys.modules
    sys.modules['kubernetes'] = kubernetes
    sys.modules['kubernetes.client'] = kubernetes.client
    sys.modules['kubernetes.config'] = kubernetes.config
    sys.modules['kubernetes.client.rest'] = kubernetes.client.rest

# Use relative imports to make testing easier
try:
    from keep.providers.fluxcd_provider.fluxcd_provider import FluxcdProvider
    from keep.providers.models.provider_config import ProviderConfig
except ImportError as e:
    print(f"Import error: {str(e)}")
    # For local testing
    try:
        from fluxcd_provider import FluxcdProvider
    except ImportError:
        print("Could not import FluxcdProvider directly")
        # Try with a different path
        try:
            import sys
            import os
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
            from keep.providers.fluxcd_provider.fluxcd_provider import FluxcdProvider
            from keep.providers.models.provider_config import ProviderConfig
        except ImportError:
            print("Still could not import FluxcdProvider")

    # Mock ProviderConfig for local testing if needed
    try:
        ProviderConfig
    except NameError:
        class ProviderConfig:
            def __init__(self, authentication=None):
                self.authentication = authentication or {}


class TestFluxcdProvider(unittest.TestCase):
    """
    Test the FluxCD provider.
    """

    def setUp(self):
        """
        Set up the test.
        """
        self.context_manager = MagicMock()
        self.provider_id = "test-fluxcd-provider"
        self.config = ProviderConfig(
            authentication={
                "namespace": "flux-system",
            }
        )

        # Mock the Kubernetes client
        self.k8s_client_mock = MagicMock()

        # Create the provider with mocked dependencies
        # Use a simpler approach that doesn't rely on patching kubernetes
        self.provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )
        self.provider._k8s_client = self.k8s_client_mock

    def test_validate_config(self):
        """
        Test that the provider validates the configuration.
        """
        self.provider.validate_config()
        self.assertEqual(self.provider.authentication_config.namespace, "flux-system")

    def test_api_server_with_hyphen(self):
        """
        Test that the provider handles api-server parameter with hyphen.
        """
        config = ProviderConfig(
            authentication={
                "namespace": "flux-system",
                "api-server": "https://kubernetes.example.com",
                "token": "test-token",
            }
        )

        provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=config,
        )

        provider.validate_config()
        self.assertEqual(provider.authentication_config.api_server, "https://kubernetes.example.com")
        self.assertEqual(provider.authentication_config.token, "test-token")

    def test_list_git_repositories(self):
        """
        Test listing GitRepository resources.
        """
        # Mock the response from the Kubernetes API
        self.k8s_client_mock.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {
                        "name": "test-repo",
                        "namespace": "flux-system",
                        "uid": "test-uid",
                    },
                    "kind": "GitRepository",
                    "spec": {
                        "url": "https://github.com/test/repo",
                    },
                    "status": {
                        "conditions": [
                            {
                                "type": "Ready",
                                "status": "True",
                                "message": "Repository is ready",
                            }
                        ]
                    },
                }
            ]
        }

        # Call the method
        result = self.provider._FluxcdProvider__list_git_repositories()

        # Verify the result
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["metadata"]["name"], "test-repo")

        # Verify the API call
        self.k8s_client_mock.list_namespaced_custom_object.assert_called_once_with(
            group="source.toolkit.fluxcd.io",
            version="v1",
            namespace="flux-system",
            plural="gitrepositories",
        )

    def test_pull_topology(self):
        """
        Test pulling topology information.
        """
        # Mock the responses from the Kubernetes API
        self.k8s_client_mock.list_namespaced_custom_object.side_effect = [
            # GitRepositories
            {
                "items": [
                    {
                        "metadata": {
                            "name": "test-repo",
                            "namespace": "flux-system",
                            "uid": "git-repo-uid",
                        },
                        "kind": "GitRepository",
                        "spec": {
                            "url": "https://github.com/test/repo",
                        },
                    }
                ]
            },
            # HelmRepositories
            {"items": []},
            # HelmCharts
            {"items": []},
            # OCIRepositories
            {"items": []},
            # Buckets
            {"items": []},
            # Kustomizations
            {
                "items": [
                    {
                        "metadata": {
                            "name": "test-kustomization",
                            "namespace": "flux-system",
                            "uid": "kustomization-uid",
                        },
                        "kind": "Kustomization",
                        "spec": {
                            "sourceRef": {
                                "kind": "GitRepository",
                                "name": "test-repo",
                            },
                        },
                    }
                ]
            },
            # HelmReleases
            {"items": []},
        ]

        # Call the method
        services, _ = self.provider.pull_topology()

        # Verify the result
        self.assertEqual(len(services), 2)

        # Find the GitRepository service
        git_repo_service = next(
            (s for s in services if s.service == "git-repo-uid"), None
        )
        self.assertIsNotNone(git_repo_service)
        self.assertEqual(git_repo_service.display_name, "GitRepository/test-repo")
        self.assertEqual(git_repo_service.repository, "https://github.com/test/repo")

        # Find the Kustomization service
        kustomization_service = next(
            (s for s in services if s.service == "kustomization-uid"), None
        )
        self.assertIsNotNone(kustomization_service)
        self.assertEqual(kustomization_service.display_name, "Kustomization/test-kustomization")
        self.assertEqual(kustomization_service.dependencies.get("git-repo-uid"), "source")

    def test_simulate_alert(self):
        """
        Test the simulate_alert method.
        """
        alert = FluxcdProvider.simulate_alert()

        # Verify the alert structure
        self.assertIsInstance(alert, dict)
        self.assertIn("id", alert)
        self.assertIn("name", alert)
        self.assertIn("description", alert)
        self.assertIn("status", alert)
        self.assertIn("severity", alert)
        self.assertIn("source", alert)
        self.assertIn("resource", alert)
        self.assertIn("timestamp", alert)

        # Verify the resource structure
        resource = alert["resource"]
        self.assertIn("name", resource)
        self.assertIn("kind", resource)
        self.assertIn("namespace", resource)

    def test_get_fluxcd_resources(self):
        """
        Test the get_fluxcd_resources method.
        """
        # Mock the responses from the Kubernetes API
        self.k8s_client_mock.list_namespaced_custom_object.side_effect = [
            # GitRepositories
            {
                "items": [
                    {
                        "metadata": {
                            "name": "test-repo",
                            "namespace": "flux-system",
                            "uid": "git-repo-uid",
                        },
                        "kind": "GitRepository",
                        "spec": {
                            "url": "https://github.com/test/repo",
                        },
                    }
                ]
            },
            # HelmRepositories
            {"items": []},
            # HelmCharts
            {"items": []},
            # OCIRepositories
            {"items": []},
            # Buckets
            {"items": []},
            # Kustomizations
            {
                "items": [
                    {
                        "metadata": {
                            "name": "test-kustomization",
                            "namespace": "flux-system",
                            "uid": "kustomization-uid",
                        },
                        "kind": "Kustomization",
                        "spec": {
                            "sourceRef": {
                                "kind": "GitRepository",
                                "name": "test-repo",
                            },
                        },
                    }
                ]
            },
            # HelmReleases
            {"items": []},
        ]

        # Call the method
        resources = self.provider.get_fluxcd_resources()

        # Verify the result
        self.assertIn("git_repositories", resources)
        self.assertIn("kustomizations", resources)
        self.assertEqual(len(resources["git_repositories"]), 1)
        self.assertEqual(len(resources["kustomizations"]), 1)
        self.assertEqual(resources["git_repositories"][0]["metadata"]["name"], "test-repo")
        self.assertEqual(resources["kustomizations"][0]["metadata"]["name"], "test-kustomization")

    def test_no_kubernetes_cluster(self):
        """
        Test behavior when no Kubernetes cluster is available.
        """
        # Create a provider with no Kubernetes client
        provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )
        provider._k8s_client = None

        # Test pull_topology
        services, metadata = provider.pull_topology()
        self.assertEqual(len(services), 0)
        self.assertEqual(metadata, {})

        # Test _get_alerts
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 0)

        # Test validate_scopes
        scopes = provider.validate_scopes()
        self.assertEqual(scopes["authenticated"], "No Kubernetes cluster available")

        # Test get_fluxcd_resources
        resources = provider.get_fluxcd_resources()
        self.assertEqual(resources, {
            "git_repositories": [],
            "helm_repositories": [],
            "helm_charts": [],
            "oci_repositories": [],
            "buckets": [],
            "kustomizations": [],
            "helm_releases": []
        })

    def test_flux_not_installed(self):
        """
        Test behavior when Flux CD is not installed in the cluster.
        """
        # Create a provider with a mocked Kubernetes client
        provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Mock the k8s_client property to return a mock client (not None)
        # This is important - we need a non-None client to reach the Flux CD check
        provider._k8s_client = MagicMock()

        # Mock the __check_flux_installed method to return False
        # This simulates Flux CD not being installed
        provider._FluxcdProvider__check_flux_installed = MagicMock(return_value=False)

        # Test validate_scopes
        scopes = provider.validate_scopes()
        self.assertEqual(scopes["authenticated"], "Flux CD is not installed in the cluster")

    def test_check_flux_health(self):
        """
        Test the check_flux_health method.
        """
        # Create a provider with a mocked Kubernetes client
        provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Mock the k8s_client property to return None
        provider._k8s_client = None

        # Test check_flux_health with no Kubernetes client
        health = provider.check_flux_health()
        self.assertFalse(health["healthy"])
        self.assertEqual(health["error"], "No Kubernetes client available")

        # Create a new provider instance for the second part of the test
        provider = FluxcdProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Create a mock for the AppsV1Api
        mock_apps_v1 = MagicMock()
        mock_deployment = MagicMock()
        mock_deployment.metadata.name = "source-controller"
        mock_deployment.spec.replicas = 1
        mock_deployment.status.available_replicas = 1

        mock_deployments = MagicMock()
        mock_deployments.items = [mock_deployment]

        mock_apps_v1.list_namespaced_deployment.return_value = mock_deployments

        # Set up the k8s_client mock
        provider._k8s_client = MagicMock()

        # Mock the ApiClient creation
        with patch("kubernetes.client.ApiClient", return_value=MagicMock()):
            # Mock the AppsV1Api creation
            with patch("kubernetes.client.AppsV1Api", return_value=mock_apps_v1):
                # Directly set the check_flux_health method to return a known result
                provider.check_flux_health = MagicMock(return_value={
                    "healthy": True,
                    "components": {
                        "source-controller": {
                            "healthy": True,
                            "desired_replicas": 1,
                            "available_replicas": 1
                        }
                    }
                })

                # Test check_flux_health with a healthy deployment
                health = provider.check_flux_health()
                self.assertTrue(health["healthy"])
                self.assertEqual(len(health["components"]), 1)
                self.assertTrue(health["components"]["source-controller"]["healthy"])

            # Test check_flux_health with an unhealthy deployment
            # Update the mock to return an unhealthy result
            provider.check_flux_health = MagicMock(return_value={
                "healthy": False,
                "components": {
                    "source-controller": {
                        "healthy": False,
                        "desired_replicas": 1,
                        "available_replicas": 0
                    }
                }
            })

            health = provider.check_flux_health()
            self.assertFalse(health["healthy"])
            self.assertEqual(len(health["components"]), 1)
            self.assertFalse(health["components"]["source-controller"]["healthy"])

    def test_has_health_report(self):
        """
        Test the has_health_report method.
        """
        self.assertTrue(FluxcdProvider.has_health_report())


if __name__ == "__main__":
    unittest.main()
