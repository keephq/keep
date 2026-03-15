"""
Tests for the Nagios provider.
"""

import pytest

from keep.providers.nagios_provider.nagios_provider import NagiosProvider
from keep.api.models.alert import AlertSeverity, AlertStatus


class TestNagiosProviderFormatAlert:
    """Test _format_alert static method for various Nagios event payloads."""

    def test_service_critical_alert(self):
        """Test formatting a critical service alert."""
        event = {
            "object_type": "service",
            "hostname": "webserver01",
            "host_alias": "Web Server 01",
            "host_address": "192.168.1.10",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "service_state_type": "HARD",
            "service_output": "HTTP CRITICAL - Socket timeout after 10 seconds",
            "long_service_output": "",
            "notification_type": "PROBLEM",
            "notification_author": "",
            "notification_comment": "",
            "date_time": "",
            "service_duration": "0d 0h 5m 30s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.name == "webserver01/HTTP"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.hostname == "webserver01"
        assert alert.ip_address == "192.168.1.10"
        assert alert.service_description == "HTTP"
        assert alert.source == ["nagios"]
        assert alert.pushed is True
        assert "Socket timeout" in alert.message

    def test_service_ok_recovery(self):
        """Test formatting a service recovery (OK) alert."""
        event = {
            "object_type": "service",
            "hostname": "webserver01",
            "host_alias": "Web Server 01",
            "host_address": "192.168.1.10",
            "service_description": "HTTP",
            "service_state": "OK",
            "service_state_type": "HARD",
            "service_output": "HTTP OK - 200 OK, 0.052s response time",
            "long_service_output": "",
            "notification_type": "RECOVERY",
            "notification_author": "",
            "notification_comment": "",
            "date_time": "",
            "service_duration": "0d 2h 15m 0s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_service_warning_alert(self):
        """Test formatting a warning service alert."""
        event = {
            "object_type": "service",
            "hostname": "dbserver01",
            "host_alias": "DB Server 01",
            "host_address": "192.168.1.20",
            "service_description": "Disk Usage",
            "service_state": "WARNING",
            "service_state_type": "HARD",
            "service_output": "DISK WARNING - /var is 85% full",
            "long_service_output": "/var: 85% used (42GB of 50GB)",
            "notification_type": "PROBLEM",
            "notification_author": "",
            "notification_comment": "",
            "date_time": "",
            "service_duration": "0d 0h 0m 30s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
        assert "85% full" in alert.message
        assert "85% used" in alert.description

    def test_host_down_alert(self):
        """Test formatting a host DOWN alert."""
        event = {
            "object_type": "host",
            "hostname": "router01",
            "host_alias": "Core Router",
            "host_address": "10.0.0.1",
            "host_state": "DOWN",
            "host_state_type": "HARD",
            "host_output": "PING CRITICAL - Packet loss = 100%",
            "long_host_output": "",
            "notification_type": "PROBLEM",
            "notification_author": "",
            "notification_comment": "",
            "date_time": "",
            "host_duration": "0d 0h 2m 0s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.name == "router01"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.hostname == "router01"
        assert alert.service_description == ""
        assert "Packet loss" in alert.message

    def test_host_up_recovery(self):
        """Test formatting a host recovery (UP) alert."""
        event = {
            "object_type": "host",
            "hostname": "router01",
            "host_alias": "Core Router",
            "host_address": "10.0.0.1",
            "host_state": "UP",
            "host_state_type": "HARD",
            "host_output": "PING OK - Packet loss = 0%, RTA = 1.5ms",
            "long_host_output": "",
            "notification_type": "RECOVERY",
            "notification_author": "",
            "notification_comment": "",
            "date_time": "",
            "host_duration": "0d 0h 15m 30s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_host_unreachable_alert(self):
        """Test formatting a host UNREACHABLE alert."""
        event = {
            "object_type": "host",
            "hostname": "switch02",
            "host_alias": "Access Switch 02",
            "host_address": "10.0.1.2",
            "host_state": "UNREACHABLE",
            "host_state_type": "HARD",
            "host_output": "Host unreachable - parent host down",
            "long_host_output": "",
            "notification_type": "PROBLEM",
            "notification_author": "",
            "notification_comment": "",
            "date_time": "",
            "host_duration": "0d 0h 0m 10s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING

    def test_acknowledgement_notification(self):
        """Test that ACKNOWLEDGEMENT notification type sets status correctly."""
        event = {
            "object_type": "service",
            "hostname": "webserver01",
            "host_alias": "Web Server 01",
            "host_address": "192.168.1.10",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "service_state_type": "HARD",
            "service_output": "HTTP CRITICAL - Connection refused",
            "long_service_output": "",
            "notification_type": "ACKNOWLEDGEMENT",
            "notification_author": "admin",
            "notification_comment": "Working on it",
            "date_time": "",
            "service_duration": "0d 1h 0m 0s",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.notification_author == "admin"
        assert alert.notification_comment == "Working on it"

    def test_alert_id_format_service(self):
        """Test that alert IDs are properly constructed for service alerts."""
        event = {
            "object_type": "service",
            "hostname": "host1",
            "service_description": "CPU Load",
            "service_state": "WARNING",
            "notification_type": "PROBLEM",
        }

        alert = NagiosProvider._format_alert(event)
        assert alert.id == "nagios-host1-CPU Load"

    def test_alert_id_format_host(self):
        """Test that alert IDs are properly constructed for host alerts."""
        event = {
            "object_type": "host",
            "hostname": "host1",
            "host_state": "DOWN",
            "notification_type": "PROBLEM",
        }

        alert = NagiosProvider._format_alert(event)
        assert alert.id == "nagios-host1"

    def test_unknown_object_type_defaults_to_host(self):
        """Test that an unknown object_type is treated as a host alert."""
        event = {
            "object_type": "unknown",
            "hostname": "server01",
            "host_state": "DOWN",
            "host_output": "Something is wrong",
            "notification_type": "PROBLEM",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.name == "server01"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_missing_fields_handled_gracefully(self):
        """Test that missing fields don't cause errors."""
        event = {
            "hostname": "minimal-host",
            "notification_type": "PROBLEM",
        }

        alert = NagiosProvider._format_alert(event)

        assert alert.hostname == "minimal-host"
        assert alert.source == ["nagios"]
        assert alert.pushed is True
