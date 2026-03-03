import unittest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.coroot_provider.coroot_provider import CorootProvider


class TestCorootProvider(unittest.TestCase):
    def test_format_alert_critical(self):
        event = {
            "Status": "CRITICAL",
            "Application": {
                "Namespace": "production",
                "Kind": "Deployment",
                "Name": "api-server",
            },
            "Reports": [
                {
                    "Name": "SLO",
                    "Check": "Availability",
                    "Message": "error budget burn rate is 26x within 1 hour",
                }
            ],
            "URL": "https://coroot.example.com/p/project1/app/production/Deployment/api-server",
        }

        alert = CorootProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.service, "api-server")
        self.assertEqual(alert.id, "coroot-production-Deployment-api-server")
        self.assertIn("Availability", alert.name)
        self.assertIn("error budget", alert.description)
        self.assertEqual(alert.source, ["coroot"])

    def test_format_alert_warning(self):
        event = {
            "Status": "WARNING",
            "Application": {"Namespace": "staging", "Kind": "StatefulSet", "Name": "redis"},
            "Reports": [{"Name": "CPU", "Check": "Usage", "Message": "CPU usage > 90%"}],
            "URL": "",
        }

        alert = CorootProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_alert_resolved(self):
        event = {
            "Status": "OK",
            "Application": {"Namespace": "prod", "Kind": "Deployment", "Name": "web"},
            "Reports": [],
            "URL": "",
        }

        alert = CorootProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertIn("web", alert.description)

    def test_format_alert_unknown_status(self):
        event = {
            "Status": "UNKNOWN",
            "Application": {"Namespace": "", "Kind": "", "Name": "svc"},
            "Reports": [],
            "URL": "",
        }

        alert = CorootProvider._format_alert(event)

        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_format_alert_empty_application(self):
        event = {"Status": "CRITICAL", "Application": {}, "Reports": [], "URL": ""}

        alert = CorootProvider._format_alert(event)

        self.assertEqual(alert.service, "unknown")


if __name__ == "__main__":
    unittest.main()
