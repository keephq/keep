"""
Tests for the Nagios provider.

Covers:
- _format_alert() for both HOST and SERVICE webhook payloads
- Status and severity mappings for all Nagios states
- Alert ID generation
- Graceful handling of missing fields
"""
import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.nagios_provider.nagios_provider import NagiosProvider


class TestFormatAlertHost:
    """Tests for HOST-type webhook payloads."""

    def test_host_down(self):
        """DOWN host maps to FIRING + CRITICAL."""
        event = {
            "type": "HOST",
            "hostname": "web-01",
            "hoststate": "DOWN",
            "hostoutput": "PING CRITICAL - Packet loss = 100%",
            "notificationtype": "PROBLEM",
            "datetime": "2024-10-26 23:20:39",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.id == "nagios-host-web-01"
        assert alert.name == "web-01"
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.host == "web-01"
        assert alert.service is None
        assert "CRITICAL" in alert.description

    def test_host_up_recovery(self):
        """UP host maps to RESOLVED."""
        event = {
            "type": "HOST",
            "hostname": "web-01",
            "hoststate": "UP",
            "hostoutput": "PING OK",
            "notificationtype": "RECOVERY",
            "datetime": "2024-10-26 23:25:00",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_host_unreachable(self):
        """UNREACHABLE maps to FIRING + HIGH severity."""
        event = {
            "type": "HOST",
            "hostname": "db-01",
            "hoststate": "UNREACHABLE",
            "hostoutput": "Host unreachable",
            "notificationtype": "PROBLEM",
            "datetime": "2024-10-26 22:00:00",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.HIGH

    def test_host_missing_optional_fields(self):
        """Missing optional fields do not raise exceptions."""
        event = {
            "type": "HOST",
            "hostname": "host-x",
            "hoststate": "DOWN",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.id == "nagios-host-host-x"
        assert alert.status == AlertStatus.FIRING


class TestFormatAlertService:
    """Tests for SERVICE-type webhook payloads."""

    def test_service_critical(self):
        """CRITICAL service maps to FIRING + CRITICAL."""
        event = {
            "type": "SERVICE",
            "hostname": "web-01",
            "servicedesc": "HTTP Check",
            "servicestate": "CRITICAL",
            "serviceoutput": "HTTP CRITICAL - Socket timeout after 10 seconds",
            "notificationtype": "PROBLEM",
            "datetime": "2024-10-26 23:20:39",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.id == "nagios-service-web-01-HTTP Check"
        assert alert.name == "HTTP Check"
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.host == "web-01"
        assert alert.service == "HTTP Check"

    def test_service_warning(self):
        """WARNING service maps to FIRING + WARNING severity."""
        event = {
            "type": "SERVICE",
            "hostname": "db-01",
            "servicedesc": "Disk Usage",
            "servicestate": "WARNING",
            "serviceoutput": "DISK WARNING - /var 85% full",
            "notificationtype": "PROBLEM",
            "datetime": "2024-10-26 23:20:39",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.WARNING

    def test_service_ok_recovery(self):
        """OK service maps to RESOLVED."""
        event = {
            "type": "SERVICE",
            "hostname": "app-01",
            "servicedesc": "CPU Load",
            "servicestate": "OK",
            "serviceoutput": "OK - load average: 0.5, 0.3, 0.2",
            "notificationtype": "RECOVERY",
            "datetime": "2024-10-26 23:30:00",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_service_unknown(self):
        """UNKNOWN service maps to FIRING + INFO severity."""
        event = {
            "type": "SERVICE",
            "hostname": "proxy-01",
            "servicedesc": "SSL Certificate",
            "servicestate": "UNKNOWN",
            "serviceoutput": "UNKNOWN: Could not connect to host",
            "notificationtype": "PROBLEM",
            "datetime": "2024-10-26 23:20:39",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.INFO

    def test_default_to_service_type(self):
        """Missing type field defaults to SERVICE handling."""
        event = {
            "hostname": "web-01",
            "servicedesc": "HTTP",
            "servicestate": "CRITICAL",
            "serviceoutput": "timeout",
            "notificationtype": "PROBLEM",
        }
        alert = NagiosProvider._format_alert(event)
        assert "service" in alert.id

    def test_source_is_nagios(self):
        """Alerts always carry source=['nagios']."""
        event = {
            "type": "SERVICE",
            "hostname": "web-01",
            "servicedesc": "HTTP",
            "servicestate": "CRITICAL",
            "serviceoutput": "timeout",
        }
        alert = NagiosProvider._format_alert(event)
        assert alert.source == ["nagios"]


class TestStatusMaps:
    """Verify all status/severity maps are complete and consistent."""

    def test_host_status_map_covers_all_states(self):
        for state in (0, 1, 2, "UP", "DOWN", "UNREACHABLE"):
            assert state in NagiosProvider.HOST_STATUS_MAP, f"Missing: {state}"

    def test_host_severity_map_covers_all_states(self):
        for state in (0, 1, 2, "UP", "DOWN", "UNREACHABLE"):
            assert state in NagiosProvider.HOST_SEVERITY_MAP, f"Missing: {state}"

    def test_service_status_map_covers_all_states(self):
        for state in (0, 1, 2, 3, "OK", "WARNING", "CRITICAL", "UNKNOWN"):
            assert state in NagiosProvider.SERVICE_STATUS_MAP, f"Missing: {state}"

    def test_service_severity_map_covers_all_states(self):
        for state in (0, 1, 2, 3, "OK", "WARNING", "CRITICAL", "UNKNOWN"):
            assert state in NagiosProvider.SERVICE_SEVERITY_MAP, f"Missing: {state}"

    def test_resolved_states_map_to_resolved(self):
        assert NagiosProvider.HOST_STATUS_MAP[0] == AlertStatus.RESOLVED
        assert NagiosProvider.HOST_STATUS_MAP["UP"] == AlertStatus.RESOLVED
        assert NagiosProvider.SERVICE_STATUS_MAP[0] == AlertStatus.RESOLVED
        assert NagiosProvider.SERVICE_STATUS_MAP["OK"] == AlertStatus.RESOLVED

    def test_problem_states_map_to_firing(self):
        assert NagiosProvider.HOST_STATUS_MAP["DOWN"] == AlertStatus.FIRING
        assert NagiosProvider.SERVICE_STATUS_MAP["CRITICAL"] == AlertStatus.FIRING
        assert NagiosProvider.SERVICE_STATUS_MAP["WARNING"] == AlertStatus.FIRING
