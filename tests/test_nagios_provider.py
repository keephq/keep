import unittest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestNagiosProvider(unittest.TestCase):
    def test_host_problem_down(self):
        alert = NagiosProvider._format_alert(
            {
                "notificationtype": "PROBLEM",
                "hostname": "web-01",
                "hoststate": "DOWN",
                "hostoutput": "Host is down",
                "shortdatetime": "2026-02-24 12:00:00",
                "hostproblemid": "h-1",
            }
        )

        self.assertEqual(alert.name, "web-01")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.source, ["nagios"])

    def test_host_recovery_up(self):
        alert = NagiosProvider._format_alert(
            {
                "notificationtype": "RECOVERY",
                "hostname": "web-01",
                "hoststate": "UP",
                "hostoutput": "PING OK",
                "shortdatetime": "2026-02-24 12:05:00",
                "hostproblemid": "h-1",
            }
        )

        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_service_critical_problem(self):
        alert = NagiosProvider._format_alert(
            {
                "notificationtype": "PROBLEM",
                "hostname": "app-01",
                "servicedesc": "HTTP",
                "servicestate": "CRITICAL",
                "serviceoutput": "500 response",
                "shortdatetime": "2026-02-24 12:10:00",
                "serviceproblemid": "s-1",
            }
        )

        self.assertEqual(alert.name, "app-01 - HTTP")
        self.assertEqual(alert.service, "HTTP")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_service_warning_problem(self):
        alert = NagiosProvider._format_alert(
            {
                "notificationtype": "PROBLEM",
                "hostname": "app-01",
                "servicedesc": "Disk",
                "servicestate": "WARNING",
                "serviceoutput": "80% used",
                "shortdatetime": "2026-02-24 12:15:00",
                "serviceproblemid": "s-2",
            }
        )

        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_service_recovery(self):
        alert = NagiosProvider._format_alert(
            {
                "notificationtype": "RECOVERY",
                "hostname": "app-01",
                "servicedesc": "HTTP",
                "servicestate": "OK",
                "serviceoutput": "200 OK",
                "shortdatetime": "2026-02-24 12:20:00",
                "serviceproblemid": "s-1",
            }
        )

        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_service_acknowledge(self):
        alert = NagiosProvider._format_alert(
            {
                "notificationtype": "ACKNOWLEDGEMENT",
                "hostname": "app-01",
                "servicedesc": "CPU",
                "servicestate": "CRITICAL",
                "serviceoutput": "95% CPU",
                "notificationcomment": "Investigating",
                "shortdatetime": "2026-02-24 12:25:00",
                "serviceproblemid": "s-3",
            }
        )

        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)
        self.assertEqual(alert.note, "Investigating")


if __name__ == "__main__":
    unittest.main()
