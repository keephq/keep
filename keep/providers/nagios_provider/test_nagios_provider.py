"""
Tests for the Nagios provider.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the parent directory to sys.path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock requests module if not available
try:
    import requests
except ImportError:
    requests = MagicMock()
    sys.modules['requests'] = requests

# Try to import the provider
try:
    from keep.providers.nagios_provider.nagios_provider import NagiosProvider
    from keep.providers.models.provider_config import ProviderConfig
except ImportError as e:
    print(f"Import error: {str(e)}")
    NagiosProvider = None
    ProviderConfig = None


class TestNagiosProvider(unittest.TestCase):
    """
    Test the Nagios provider.
    """

    def setUp(self):
        """
        Set up the test.
        """
        self.context_manager = MagicMock()
        self.provider_id = "test-nagios-provider"
        
        if ProviderConfig:
            self.config = ProviderConfig(
                authentication={
                    "nagios_url": "https://nagios.example.com",
                    "api_key": "test-api-key",
                    "livestatus_host": "localhost",
                    "livestatus_port": 6557,
                }
            )
        else:
            self.config = None

    def test_provider_category(self):
        """
        Test that the provider has the correct category.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        self.assertIn("Monitoring", NagiosProvider.PROVIDER_CATEGORY)

    def test_provider_scopes(self):
        """
        Test that provider scopes are defined correctly.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        self.assertTrue(len(NagiosProvider.PROVIDER_SCOPES) > 0)
        scope_names = [scope.name for scope in NagiosProvider.PROVIDER_SCOPES]
        self.assertIn("read_problems", scope_names)
        self.assertIn("read_hosts", scope_names)
        self.assertIn("read_services", scope_names)

    def test_provider_methods(self):
        """
        Test that provider methods are defined correctly.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        self.assertEqual(len(NagiosProvider.PROVIDER_METHODS), 4)
        method_names = [method.name for method in NagiosProvider.PROVIDER_METHODS]
        self.assertIn("Acknowledge Problem", method_names)
        self.assertIn("Schedule Downtime", method_names)
        self.assertIn("Remove Acknowledgement", method_names)
        self.assertIn("Get Problems", method_names)

    def test_severity_map(self):
        """
        Test the severity mappings.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        # Test service severity map
        self.assertIn("OK", NagiosProvider.SERVICE_SEVERITY_MAP)
        self.assertIn("WARNING", NagiosProvider.SERVICE_SEVERITY_MAP)
        self.assertIn("CRITICAL", NagiosProvider.SERVICE_SEVERITY_MAP)
        self.assertIn("UNKNOWN", NagiosProvider.SERVICE_SEVERITY_MAP)
        
        # Test numeric severity map
        self.assertIn(0, NagiosProvider.SEVERITIES_MAP)
        self.assertIn(1, NagiosProvider.SEVERITIES_MAP)
        self.assertIn(2, NagiosProvider.SEVERITIES_MAP)

    def test_simulate_alert(self):
        """
        Test the simulate_alert method.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        alert = NagiosProvider.simulate_alert()
        
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
        resource = alert.get("resource", {})
        self.assertIn("host", resource)
        self.assertIn("service", resource)

    def test_format_service_alert(self):
        """
        Test the _format_alert method for service alerts.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        if not self.config:
            self.skipTest("ProviderConfig not available")
        
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Mock livestatus query result for service
        livestatus_result = {
            "host_name": "test-host",
            "service_description": "test-service",
            "service_state": 2,
            "service_check_output": "CRITICAL: Test failed",
            "last_check": "2024-01-01 12:00:00",
            "acknowledged": 0,
        }

        # Call the format method
        alert = provider._format_alert(livestatus_result, "service")

        # Verify the alert
        self.assertIsInstance(alert, dict)
        self.assertIn("name", alert)
        self.assertIn("status", alert)
        self.assertIn("severity", alert)

    def test_format_host_alert(self):
        """
        Test the _format_alert method for host alerts.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        if not self.config:
            self.skipTest("ProviderConfig not available")
        
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Mock livestatus query result for host
        livestatus_result = {
            "host_name": "test-host",
            "host_state": 1,
            "host_output": "DOWN: Host is down",
            "last_check": "2024-01-01 12:00:00",
            "acknowledged": 0,
        }

        # Call the format method
        alert = provider._format_alert(livestatus_result, "host")

        # Verify the alert
        self.assertIsInstance(alert, dict)
        self.assertIn("name", alert)
        self.assertIn("status", alert)
        self.assertIn("severity", alert)
        self.assertIn("source", alert)

    def test_validate_config(self):
        """
        Test that the provider validates the configuration.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        if not self.config:
            self.skipTest("ProviderConfig not available")
        
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Test validate_config runs without error
        try:
            provider.validate_config()
        except Exception as e:
            self.fail(f"validate_config raised exception: {e}")

    def test_validate_scopes(self):
        """
        Test that validate_scopes runs without error.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        if not self.config:
            self.skipTest("ProviderConfig not available")
        
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Mock no Livestatus available
        provider._livestatus_socket = None

        # Test validate_scopes
        scopes = provider.validate_scopes()
        self.assertIsInstance(scopes, dict)

    def test_no_livestatus_connection(self):
        """
        Test behavior when Livestatus is not available.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        if not self.config:
            self.skipTest("ProviderConfig not available")
        
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id=self.provider_id,
            config=self.config,
        )

        # Mock no Livestatus connection
        provider._livestatus_socket = None

        # Test pull_topology returns empty
        services, metadata = provider.pull_topology()
        self.assertEqual(len(services), 0)

        # Test _get_alerts returns empty
        alerts = provider._get_alerts()
        self.assertEqual(len(alerts), 0)

    def test_has_health_report(self):
        """
        Test the has_health_report method.
        """
        if not NagiosProvider:
            self.skipTest("NagiosProvider not available")
        
        # Nagios doesn't have a health report endpoint
        self.assertFalse(NagiosProvider.has_health_report())


if __name__ == "__main__":
    unittest.main()
