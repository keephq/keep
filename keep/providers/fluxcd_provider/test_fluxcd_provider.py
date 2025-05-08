"""
Tests for the FluxCD provider.
"""

import unittest
from unittest.mock import MagicMock, patch

from keep.providers.fluxcd_provider.fluxcd_provider import FluxcdProvider
from keep.providers.models.provider_config import ProviderConfig


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
        with patch("kubernetes.config.load_incluster_config"):
            with patch("kubernetes.client.CustomObjectsApi") as mock_custom_objects_api:
                mock_custom_objects_api.return_value = self.k8s_client_mock
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


if __name__ == "__main__":
    unittest.main()
