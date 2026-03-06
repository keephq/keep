"""
Unit tests for the Nagios provider's _format_alert static method and mappings.
"""

import hashlib
import unittest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProviderFormatAlert(unittest.TestCase):
    """Tests for NagiosProvider._format_alert."""

    def test_service_critical(self):
        event = {
            "host_name": "web-server-01",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "output": "CRITICAL - Socket timeout after 10 seconds",
            "timestamp": "2025-01-15T10:30:00Z",
            "notification_type": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)

        expected_id = hashlib.sha256(b"web-server-01:HTTP").hexdigest()[:16]
        self.assertEqual(alert.id, expected_id)
        self.assertEqual(alert.name, "HTTP on web-server-01")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.description, "CRITICAL - Socket timeout after 10 seconds")
        self.assertEqual(alert.hostname, "web-server-01")
        self.assertEqual(alert.service, "HTTP")
        self.assertEqual(alert.source, ["nagios"])

    def test_service_warning(self):
        event = {
            "host_name": "db-server-01",
            "service_description": "Disk Usage",
            "service_state": "WARNING",
            "output": "WARNING - Disk usage at 85%",
            "timestamp": "2025-01-15T10:35:00Z",
            "notification_type": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_service_recovery(self):
        event = {
            "host_name": "web-server-01",
            "service_description": "HTTP",
            "service_state": "OK",
            "output": "OK - HTTP response time 0.5s",
            "timestamp": "2025-01-15T10:40:00Z",
            "notification_type": "RECOVERY",
        }
        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_host_down(self):
        event = {
            "host_name": "app-server-02",
            "host_state": "DOWN",
            "output": "CRITICAL - Host unreachable (10.0.1.5)",
            "timestamp": "2025-01-15T10:45:00Z",
            "notification_type": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)

        expected_id = hashlib.sha256(b"app-server-02:HOST").hexdigest()[:16]
        self.assertEqual(alert.id, expected_id)
        self.assertEqual(alert.name, "Host app-server-02")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertIsNone(alert.service)

    def test_host_recovery(self):
        event = {
            "host_name": "app-server-02",
            "host_state": "UP",
            "output": "OK - Host is alive",
            "timestamp": "2025-01-15T10:50:00Z",
            "notification_type": "RECOVERY",
        }
        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_acknowledgement(self):
        event = {
            "host_name": "web-server-01",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "output": "CRITICAL - Socket timeout",
            "timestamp": "2025-01-15T10:55:00Z",
            "notification_type": "ACKNOWLEDGEMENT",
        }
        alert = NagiosProvider._format_alert(event)

        # ACKNOWLEDGEMENT overrides state-based status mapping
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)
        # Severity still comes from service_state
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_host_unreachable(self):
        event = {
            "host_name": "remote-office-gw",
            "host_state": "UNREACHABLE",
            "output": "CRITICAL - Network path unreachable",
            "timestamp": "2025-01-15T11:00:00Z",
            "notification_type": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.HIGH)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_service_unknown(self):
        event = {
            "host_name": "monitoring-server",
            "service_description": "SNMP Check",
            "service_state": "UNKNOWN",
            "output": "UNKNOWN - SNMP timeout",
            "timestamp": "2025-01-15T11:05:00Z",
            "notification_type": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_returns_alertdto_instance(self):
        event = {
            "host_name": "test-host",
            "host_state": "DOWN",
            "output": "Host down",
            "notification_type": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)
        self.assertIsInstance(alert, AlertDto)

    def test_deterministic_fingerprint(self):
        """The same host+service always produces the same alert ID."""
        event = {
            "host_name": "web-server-01",
            "service_description": "HTTP",
            "service_state": "WARNING",
            "output": "first run",
            "notification_type": "PROBLEM",
        }
        alert1 = NagiosProvider._format_alert(event)

        event["output"] = "second run"
        alert2 = NagiosProvider._format_alert(event)

        self.assertEqual(alert1.id, alert2.id)


class TestNagiosProviderMappings(unittest.TestCase):
    """Tests for class-level severity and status maps."""

    def test_severity_map_completeness(self):
        expected_keys = {"OK", "WARNING", "CRITICAL", "UNKNOWN", "UP", "DOWN", "UNREACHABLE"}
        self.assertEqual(set(NagiosProvider.SEVERITY_MAP.keys()), expected_keys)

    def test_status_map_completeness(self):
        expected_keys = {"OK", "WARNING", "CRITICAL", "UNKNOWN", "UP", "DOWN", "UNREACHABLE"}
        self.assertEqual(set(NagiosProvider.STATUS_MAP.keys()), expected_keys)

    def test_service_state_numeric_maps(self):
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_SEVERITY[0], AlertSeverity.INFO)
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_SEVERITY[1], AlertSeverity.WARNING)
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_SEVERITY[2], AlertSeverity.CRITICAL)
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_SEVERITY[3], AlertSeverity.INFO)

        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_STATUS[0], AlertStatus.RESOLVED)
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_STATUS[1], AlertStatus.FIRING)
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_STATUS[2], AlertStatus.FIRING)
        self.assertEqual(NagiosProvider.SERVICE_STATE_TO_STATUS[3], AlertStatus.FIRING)

    def test_host_state_numeric_maps(self):
        self.assertEqual(NagiosProvider.HOST_STATE_TO_SEVERITY[0], AlertSeverity.INFO)
        self.assertEqual(NagiosProvider.HOST_STATE_TO_SEVERITY[1], AlertSeverity.CRITICAL)
        self.assertEqual(NagiosProvider.HOST_STATE_TO_SEVERITY[2], AlertSeverity.HIGH)

        self.assertEqual(NagiosProvider.HOST_STATE_TO_STATUS[0], AlertStatus.RESOLVED)
        self.assertEqual(NagiosProvider.HOST_STATE_TO_STATUS[1], AlertStatus.FIRING)
        self.assertEqual(NagiosProvider.HOST_STATE_TO_STATUS[2], AlertStatus.FIRING)

    def test_notification_type_to_status(self):
        self.assertEqual(
            NagiosProvider.NOTIFICATION_TYPE_TO_STATUS["PROBLEM"], AlertStatus.FIRING
        )
        self.assertEqual(
            NagiosProvider.NOTIFICATION_TYPE_TO_STATUS["RECOVERY"], AlertStatus.RESOLVED
        )
        self.assertEqual(
            NagiosProvider.NOTIFICATION_TYPE_TO_STATUS["ACKNOWLEDGEMENT"],
            AlertStatus.ACKNOWLEDGED,
        )


if __name__ == "__main__":
    unittest.main()
