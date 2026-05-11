import unittest
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProvider(unittest.TestCase):
    def test_format_service_alert_critical(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "webserver01",
            "host_address": "192.168.1.10",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "service_output": "CRITICAL - Connection refused on port 80",
            "last_check": "2024-01-15T10:30:00Z",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.name, "webserver01/HTTP")
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.description, "CRITICAL - Connection refused on port 80")
        self.assertEqual(alert.hostname, "webserver01")
        self.assertEqual(alert.service_name, "HTTP")
        self.assertEqual(alert.source, ["nagios"])

    def test_format_service_alert_warning(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "dbserver01",
            "service_description": "Disk Usage",
            "service_state": "WARNING",
            "service_output": "WARNING - Disk usage 85%",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.WARNING)

    def test_format_service_recovery(self):
        event = {
            "notification_type": "RECOVERY",
            "host_name": "webserver01",
            "service_description": "HTTP",
            "service_state": "OK",
            "service_output": "HTTP OK - 200 response",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_format_host_alert_down(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "router01",
            "host_state": "DOWN",
            "host_output": "CRITICAL - Host Unreachable",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.name, "router01")
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_format_host_recovery(self):
        event = {
            "notification_type": "RECOVERY",
            "host_name": "router01",
            "host_state": "UP",
            "host_output": "PING OK - Packet loss = 0%",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_format_unknown_state(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "server01",
            "service_description": "Custom Check",
            "service_state": "UNKNOWN",
            "service_output": "UNKNOWN - Plugin error",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_format_numeric_state_service(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "server01",
            "service_description": "CPU",
            "service_state": "2",  # CRITICAL
            "service_output": "CRITICAL - CPU 95%",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_numeric_state_host(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "router01",
            "host_state": "1",  # DOWN
            "host_output": "Host is down",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_lowercase_states(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "server01",
            "service_description": "Memory",
            "service_state": "critical",
            "service_output": "critical - memory high",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_format_acknowledgement(self):
        event = {
            "notification_type": "ACKNOWLEDGEMENT",
            "host_name": "server01",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "service_output": "Acknowledged by admin",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_format_flapping_start(self):
        event = {
            "notification_type": "FLAPPINGSTART",
            "host_name": "server01",
            "service_description": "HTTP",
            "service_state": "WARNING",
            "service_output": "Service is flapping",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_unreachable_host(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "router02",
            "host_state": "UNREACHABLE",
            "host_output": "Host is unreachable",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_alert_id_and_fingerprint(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "webserver01",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "service_output": "Down",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.id, "webserver01:HTTP")

    def test_format_host_alert_id(self):
        event = {
            "notification_type": "PROBLEM",
            "host_name": "router01",
            "host_state": "DOWN",
            "host_output": "Down",
        }

        alert = NagiosProvider._format_alert(event)
        self.assertEqual(alert.id, "router01")


if __name__ == "__main__":
    unittest.main()
