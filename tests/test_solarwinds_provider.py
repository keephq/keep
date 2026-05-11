import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.solarwinds_provider.solarwinds_provider import SolarWindsProvider


class TestSolarWindsProvider(unittest.TestCase):
    def _make_provider(self):
        ctx = MagicMock()
        ctx.event_context = None
        config = MagicMock()
        config.authentication = {
            "host_url": "https://solarwinds.example.com",
            "username": "admin",
            "password": "secret",
        }
        provider = object.__new__(SolarWindsProvider)
        provider.context_manager = ctx
        provider.logger = MagicMock()
        provider.config = config
        provider.authentication_config = MagicMock()
        provider.authentication_config.host_url = "https://solarwinds.example.com"
        provider.authentication_config.username = "admin"
        provider.authentication_config.password = "secret"
        return provider

    def test_format_alert_host_notification(self):
        event = {
            "alert_id": "12345",
            "alert_name": "Node Down",
            "node_name": "router-01",
            "severity": "CRITICAL",
            "status": "ACTIVE",
            "message": "Node router-01 is down",
            "timestamp": "2024-01-15T10:30:00Z",
        }
        alert = SolarWindsProvider._format_alert(event)
        self.assertEqual(alert.id, "12345")
        self.assertEqual(alert.name, "Node Down")
        self.assertEqual(alert.host, "router-01")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.description, "Node router-01 is down")
        self.assertEqual(alert.lastReceived, "2024-01-15T10:30:00Z")
        self.assertEqual(alert.source, ["solarwinds"])

    def test_format_alert_service_notification(self):
        event = {
            "id": "67890",
            "name": "High CPU",
            "host": "server-02",
            "Severity": "WARNING",
            "alert_status": "ACTIVE",
            "AlertMessage": "CPU usage exceeded 90%",
            "last_received": "2024-01-15T11:00:00Z",
            "custom_field": "extra_value",
        }
        alert = SolarWindsProvider._format_alert(event)
        self.assertEqual(alert.id, "67890")
        self.assertEqual(alert.name, "High CPU")
        self.assertEqual(alert.host, "server-02")
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.description, "CPU usage exceeded 90%")
        self.assertEqual(alert.custom_field, "extra_value")

    def test_format_alert_resolved(self):
        event = {
            "alert_id": "11111",
            "alert_name": "Interface Down",
            "node_name": "switch-01",
            "severity": "OK",
            "status": "RESOLVED",
            "message": "Interface recovered",
        }
        alert = SolarWindsProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_format_alert_unknown_severity(self):
        event = {
            "id": "22222",
            "name": "Unknown Event",
            "host": "device-03",
            "severity": "CUSTOM",
            "status": "ACTIVE",
        }
        alert = SolarWindsProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_alert_acknowledged(self):
        event = {
            "id": "33333",
            "name": "Disk Full",
            "host": "db-server",
            "severity": "CRITICAL",
            "Status": "ACKNOWLEDGED",
        }
        alert = SolarWindsProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)

    def test_severity_map_coverage(self):
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["CRITICAL"], AlertSeverity.CRITICAL
        )
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["WARNING"], AlertSeverity.WARNING
        )
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["WARNING_ALERT"], AlertSeverity.WARNING
        )
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["OK"], AlertSeverity.INFO
        )
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["INFORMATIONAL"], AlertSeverity.INFO
        )
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["INFO"], AlertSeverity.INFO
        )
        self.assertEqual(
            SolarWindsProvider.SEVERITY_MAP["UNKNOWN"], AlertSeverity.INFO
        )

    def test_status_map_coverage(self):
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["ACTIVE"], AlertStatus.FIRING
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["DOWN"], AlertStatus.FIRING
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["CRITICAL"], AlertStatus.FIRING
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["ACKNOWLEDGED"], AlertStatus.ACKNOWLEDGED
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["RESOLVED"], AlertStatus.RESOLVED
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["UP"], AlertStatus.RESOLVED
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["RECOVERED"], AlertStatus.RESOLVED
        )
        self.assertEqual(
            SolarWindsProvider.STATUS_MAP["OK"], AlertStatus.RESOLVED
        )

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.get")
    def test_get_alerts_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "results": [
                {
                    "AlertID": 101,
                    "AlertName": "Node Down",
                    "NodeName": "router-01",
                    "Severity": "Critical",
                    "AlertMessage": "Node is unreachable",
                    "AlertTriggerTime": "2024-01-15T10:30:00Z",
                    "Acknowledged": False,
                },
                {
                    "AlertID": 102,
                    "AlertName": "High Memory",
                    "NodeName": "server-02",
                    "Severity": "Warning",
                    "AlertMessage": "Memory usage > 85%",
                    "AlertTriggerTime": "2024-01-15T10:35:00Z",
                    "Acknowledged": True,
                },
            ]
        }
        mock_get.return_value = mock_response

        provider = self._make_provider()
        alerts = provider._get_alerts()

        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0].id, "101")
        self.assertEqual(alerts[0].name, "Node Down")
        self.assertEqual(alerts[0].severity, AlertSeverity.CRITICAL)
        self.assertEqual(alerts[0].status, AlertStatus.FIRING)
        self.assertEqual(alerts[1].id, "102")
        self.assertEqual(alerts[1].status, AlertStatus.ACKNOWLEDGED)

    @patch("keep.providers.solarwinds_provider.solarwinds_provider.requests.get")
    def test_get_alerts_api_failure(self, mock_get):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        provider = self._make_provider()
        from keep.exceptions.provider_exception import ProviderException

        with self.assertRaises(ProviderException):
            provider._get_alerts()

    def test_validate_config(self):
        provider = self._make_provider()
        provider.validate_config = SolarWindsProvider.validate_config.__get__(
            provider, SolarWindsProvider
        )
        provider.validate_config()
        self.assertEqual(provider.authentication_config.host_url, "https://solarwinds.example.com")
        self.assertEqual(provider.authentication_config.username, "admin")
        self.assertEqual(provider.authentication_config.password, "secret")


if __name__ == "__main__":
    unittest.main()
