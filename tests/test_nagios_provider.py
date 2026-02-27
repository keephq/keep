import unittest
from unittest.mock import Mock, patch, MagicMock

from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProvider(unittest.TestCase):
    def setUp(self):
        self.context_manager = Mock()
        self.config = Mock()
        self.config.authentication = {
            "host_url": "https://nagios.example.com",
            "nrdp_token": "test-token",
            "api_type": "nrdp",
        }

    def test_provider_initialization(self):
        """Test that the provider can be initialized."""
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        self.assertEqual(provider.PROVIDER_DISPLAY_NAME, "Nagios")
        self.assertIn("Monitoring", provider.PROVIDER_CATEGORY)

    def test_validate_config_nrdp(self):
        """Test NRDP configuration validation."""
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        # Should not raise
        provider.validate_config()
        self.assertEqual(provider.authentication_config.api_type, "nrdp")
        self.assertEqual(provider.authentication_config.nrdp_token, "test-token")

    def test_validate_config_cgi(self):
        """Test CGI configuration validation."""
        self.config.authentication = {
            "host_url": "https://nagios.example.com",
            "username": "admin",
            "password": "secret",
            "api_type": "cgi",
        }
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        # Should not raise
        provider.validate_config()
        self.assertEqual(provider.authentication_config.api_type, "cgi")

    def test_validate_config_missing_nrdp_token(self):
        """Test that validation fails when NRDP token is missing."""
        self.config.authentication = {
            "host_url": "https://nagios.example.com",
            "api_type": "nrdp",
        }
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        with self.assertRaises(Exception) as context:
            provider.validate_config()
        self.assertIn("NRDP token is required", str(context.exception))

    def test_validate_config_missing_cgi_creds(self):
        """Test that validation fails when CGI credentials are missing."""
        self.config.authentication = {
            "host_url": "https://nagios.example.com",
            "api_type": "cgi",
        }
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        with self.assertRaises(Exception) as context:
            provider.validate_config()
        self.assertIn("Username and password are required", str(context.exception))

    @patch("keep.providers.nagios_provider.nagios_provider.requests.post")
    def test_validate_scopes_nrdp_success(self, mock_post):
        """Test successful scope validation with NRDP."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": {"code": 0}}
        mock_post.return_value = mock_response

        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        provider.validate_config()
        scopes = provider.validate_scopes()
        
        self.assertEqual(scopes["authenticated"], True)

    @patch("keep.providers.nagios_provider.nagios_provider.requests.post")
    def test_validate_scopes_nrdp_failure(self, mock_post):
        """Test failed scope validation with NRDP."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": {"code": 1, "message": "Invalid token"}}
        mock_post.return_value = mock_response

        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        provider.validate_config()
        scopes = provider.validate_scopes()
        
        self.assertIn("Invalid token", scopes["authenticated"])

    @patch("keep.providers.nagios_provider.nagios_provider.requests.post")
    def test_get_alerts_nrdp(self, mock_post):
        """Test getting alerts from NRDP."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {"code": 0},
            "data": [
                {
                    "host_name": "server1.example.com",
                    "current_state": 2,  # DOWN
                    "plugin_output": "CRITICAL - Host Unreachable",
                    "last_check": 1704067200,
                    "problem_has_been_acknowledged": 0,
                }
            ]
        }
        mock_post.return_value = mock_response

        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        provider.validate_config()
        
        # Mock the __get_service_alerts_nrdp to return empty list
        provider._NagiosProvider__get_service_alerts_nrdp = Mock(return_value=[])
        
        alerts = provider._get_alerts()
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].name, "server1.example.com")

    def test_status_mapping(self):
        """Test that Nagios status codes map correctly to Keep statuses."""
        provider = NagiosProvider(
            context_manager=self.context_manager,
            provider_id="nagios-test",
            config=self.config,
        )
        
        from keep.api.models.alert import AlertStatus, AlertSeverity
        
        self.assertEqual(provider.STATUS_MAP[0], AlertStatus.RESOLVED)
        self.assertEqual(provider.STATUS_MAP[1], AlertStatus.FIRING)
        self.assertEqual(provider.STATUS_MAP[2], AlertStatus.FIRING)
        self.assertEqual(provider.STATUS_MAP[3], AlertStatus.FIRING)
        
        self.assertEqual(provider.SEVERITY_MAP[0], AlertSeverity.LOW)
        self.assertEqual(provider.SEVERITY_MAP[1], AlertSeverity.WARNING)
        self.assertEqual(provider.SEVERITY_MAP[2], AlertSeverity.CRITICAL)
        self.assertEqual(provider.SEVERITY_MAP[3], AlertSeverity.INFO)


if __name__ == "__main__":
    unittest.main()
