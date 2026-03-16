import unittest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProvider(unittest.TestCase):
    """Tests for the Nagios provider webhook formatting."""

    def test_format_service_problem(self):
        event = {
            "notification_type": "PROBLEM",
            "host": "webserver01",
            "host_alias": "Web Server 01",
            "host_address": "192.168.1.100",
            "service": "HTTP",
            "state": "CRITICAL",
            "output": "HTTP CRITICAL - Socket timeout after 10 seconds",
            "long_output": "",
            "timestamp": "1706300400",
            "attempt": "3",
            "max_attempts": "3",
            "state_type": "HARD",
            "notification_author": "",
            "notification_comment": "",
            "contact_name": "admin",
            "contact_email": "admin@example.com",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.name, "HTTP")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.host, "webserver01")
        self.assertEqual(alert.service, "HTTP")
        self.assertIn("nagios", alert.source)

    def test_format_service_recovery(self):
        event = {
            "notification_type": "RECOVERY",
            "host": "webserver01",
            "host_alias": "Web Server 01",
            "host_address": "192.168.1.100",
            "service": "HTTP",
            "state": "OK",
            "output": "HTTP OK - 200 response in 0.5s",
            "long_output": "",
            "timestamp": "1706300500",
            "attempt": "1",
            "max_attempts": "3",
            "state_type": "HARD",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_format_host_down(self):
        event = {
            "notification_type": "PROBLEM",
            "host": "dbserver01",
            "host_alias": "Database Server",
            "host_address": "192.168.1.200",
            "state": "DOWN",
            "output": "PING CRITICAL - Packet loss = 100%",
            "long_output": "rta=0.000ms;3000.000;5000.000;0; pl=100%;80;100;; rtmax=0.000ms;;;; rtmin=0.000ms;;;;",
            "timestamp": "1706300600",
            "attempt": "3",
            "max_attempts": "3",
            "state_type": "HARD",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.name, "Host DOWN")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.host, "dbserver01")
        self.assertIsNone(alert.service)
        self.assertIn("PING CRITICAL", alert.description)

    def test_format_host_recovery(self):
        event = {
            "notification_type": "RECOVERY",
            "host": "dbserver01",
            "host_alias": "Database Server",
            "host_address": "192.168.1.200",
            "state": "UP",
            "output": "PING OK - Packet loss = 0%, RTA = 0.80 ms",
            "timestamp": "1706300700",
            "attempt": "1",
            "max_attempts": "3",
            "state_type": "HARD",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_format_acknowledgement(self):
        event = {
            "notification_type": "ACKNOWLEDGEMENT",
            "host": "webserver01",
            "service": "HTTP",
            "state": "CRITICAL",
            "output": "HTTP CRITICAL - Socket timeout",
            "timestamp": "1706300800",
            "notification_author": "admin",
            "notification_comment": "Looking into it",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)

    def test_format_downtime(self):
        event = {
            "notification_type": "DOWNTIMESTART",
            "host": "webserver01",
            "service": "HTTP",
            "state": "OK",
            "output": "Scheduled downtime",
            "timestamp": "1706300900",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.status, AlertStatus.SUPPRESSED)

    def test_format_warning_severity(self):
        event = {
            "notification_type": "PROBLEM",
            "host": "webserver01",
            "service": "Disk",
            "state": "WARNING",
            "output": "DISK WARNING - /var is 85% full",
            "timestamp": "1706301000",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_long_output_concatenated(self):
        event = {
            "notification_type": "PROBLEM",
            "host": "webserver01",
            "service": "HTTP",
            "state": "CRITICAL",
            "output": "HTTP CRITICAL",
            "long_output": "Additional details here",
            "timestamp": "1706301100",
        }

        alert = NagiosProvider._format_alert(event)

        self.assertIn("HTTP CRITICAL", alert.description)
        self.assertIn("Additional details here", alert.description)

    def test_fingerprint_fields(self):
        self.assertEqual(
            NagiosProvider.FINGERPRINT_FIELDS, ["host", "service", "name"]
        )

    def test_provider_metadata(self):
        self.assertEqual(NagiosProvider.PROVIDER_DISPLAY_NAME, "Nagios")
        self.assertIn("alert", NagiosProvider.PROVIDER_TAGS)
        self.assertIn("Monitoring", NagiosProvider.PROVIDER_CATEGORY)


if __name__ == "__main__":
    unittest.main()
