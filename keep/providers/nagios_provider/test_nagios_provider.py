import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProvider(unittest.TestCase):
    def setUp(self):
        self.context_manager = MagicMock(spec=ContextManager)
        self.context_manager.tenant_id = "singletenant"
        self.provider_config = ProviderConfig(
            authentication={
                "nagios_url": "https://nagios.example.com/nagiosxi",
                "api_key": "test_api_key",
            }
        )
        self.provider = NagiosProvider(
            self.context_manager, provider_id="nagios", config=self.provider_config
        )
        self.provider.validate_config()

    @patch("keep.providers.nagios_provider.nagios_provider.requests.get")
    def test_get_alerts(self, mock_get):
        # Mock host status response
        mock_host_response = MagicMock()
        mock_host_response.json.return_value = {
            "hoststatuslist": {
                "hoststatus": [
                    {
                        "host_name": "host1",
                        "current_state": "1",
                        "status_text": "Host is DOWN",
                        "last_check": "2023-01-01 00:00:00",
                    },
                    {
                        "host_name": "host2",
                        "current_state": "0",
                        "status_text": "Host is UP",
                        "last_check": "2023-01-01 00:00:00",
                    },
                ]
            }
        }
        mock_host_response.raise_for_status.return_value = None

        # Mock service status response
        mock_service_response = MagicMock()
        mock_service_response.json.return_value = {
            "servicestatuslist": {
                "servicestatus": [
                    {
                        "host_name": "host1",
                        "service_description": "service1",
                        "current_state": "2",
                        "status_text": "Service is CRITICAL",
                        "last_check": "2023-01-01 00:00:00",
                    }
                ]
            }
        }
        mock_service_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_host_response, mock_service_response]

        alerts = self.provider._get_alerts()

        self.assertEqual(len(alerts), 2)

        # Check host alert
        self.assertEqual(alerts[0].id, "host:host1")
        self.assertEqual(alerts[0].status, AlertStatus.FIRING)
        self.assertEqual(alerts[0].severity, AlertSeverity.CRITICAL)

        # Check service alert
        self.assertEqual(alerts[1].id, "service:host1:service1")
        self.assertEqual(alerts[1].status, AlertStatus.FIRING)
        self.assertEqual(alerts[1].severity, AlertSeverity.CRITICAL)

    def test_format_alert_service(self):
        event = {
            "host_name": "host1",
            "service_description": "service1",
            "state": "2",
            "output": "Service is CRITICAL",
        }
        alert = self.provider._format_alert(event)
        self.assertEqual(alert.id, "service:host1:service1")
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_format_alert_host(self):
        event = {
            "host_name": "host1",
            "state": "1",
            "output": "Host is DOWN",
        }
        alert = self.provider._format_alert(event)
        self.assertEqual(alert.id, "host:host1")
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
