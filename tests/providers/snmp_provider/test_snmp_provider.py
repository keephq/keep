"""
Unit tests for the SNMP webhook provider.

These tests exercise _format_alert() and _resolve_severity() directly —
no network or SNMP library required.
"""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


class TestResolveSeverity:
    """Severity resolution from OID and explicit severity field."""

    def test_linkdown_oid_maps_to_high(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.3"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.HIGH

    def test_coldstart_oid_maps_to_low(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.1"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.LOW

    def test_warmstart_oid_maps_to_low(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.2"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.LOW

    def test_linkup_oid_maps_to_info(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.4"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.INFO

    def test_authentication_failure_oid_maps_to_warning(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.5"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.WARNING

    def test_explicit_severity_overrides_oid(self):
        # OID says HIGH (linkDown) but explicit severity wins
        event = {"oid": "1.3.6.1.6.3.1.1.5.3", "severity": "critical"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.CRITICAL

    def test_explicit_severity_case_insensitive(self):
        event = {"severity": "WARNING"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.WARNING

    def test_unknown_oid_defaults_to_info(self):
        event = {"oid": "1.3.6.1.4.1.99999.1.2.3"}
        assert SnmpProvider._resolve_severity(event) == AlertSeverity.INFO

    def test_empty_event_defaults_to_info(self):
        assert SnmpProvider._resolve_severity({}) == AlertSeverity.INFO


class TestFormatAlert:
    """Alert parsing from incoming JSON trap payloads."""

    def test_linkdown_trap_full_payload(self):
        event = {
            "oid": "1.3.6.1.6.3.1.1.5.3",
            "host": "192.168.1.10",
            "message": "linkDown on interface eth0",
            "severity": "high",
            "uptime": "3:14:15.00",
            "variables": {"1.3.6.1.2.1.2.2.1.8.2": "2"},
        }
        alert = SnmpProvider._format_alert(event)

        assert alert.severity == AlertSeverity.HIGH
        assert alert.host == "192.168.1.10"
        assert alert.description == "linkDown on interface eth0"
        assert alert.source == ["snmp"]
        assert alert.status == AlertStatus.FIRING
        assert alert.oid == "1.3.6.1.6.3.1.1.5.3"
        assert alert.variables == {"1.3.6.1.2.1.2.2.1.8.2": "2"}

    def test_coldstart_trap(self):
        event = {
            "oid": "1.3.6.1.6.3.1.1.5.1",
            "host": "10.0.0.5",
            "message": "coldStart: device rebooted",
        }
        alert = SnmpProvider._format_alert(event)

        assert alert.severity == AlertSeverity.LOW
        assert alert.host == "10.0.0.5"
        assert alert.source == ["snmp"]

    def test_enterprise_specific_trap_with_critical_severity(self):
        event = {
            "oid": "1.3.6.1.4.1.9.9.41.2",
            "host": "switch-core-01.example.com",
            "message": "CPU threshold exceeded (95%)",
            "severity": "critical",
            "variables": {"1.3.6.1.4.1.9.9.41.1.2.3.1.5": "95"},
        }
        alert = SnmpProvider._format_alert(event)

        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.host == "switch-core-01.example.com"

    def test_missing_host_defaults_to_unknown(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.3", "message": "trap without host"}
        alert = SnmpProvider._format_alert(event)
        assert alert.host == "unknown"

    def test_missing_message_falls_back_to_oid(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.3"}
        alert = SnmpProvider._format_alert(event)
        assert alert.description == "1.3.6.1.6.3.1.1.5.3"

    def test_missing_oid_and_message_defaults_gracefully(self):
        alert = SnmpProvider._format_alert({})
        assert alert.source == ["snmp"]
        assert alert.description == "SNMP Trap"
        assert alert.severity == AlertSeverity.INFO

    def test_msg_field_alias_used_as_description(self):
        event = {"msg": "alternate message field"}
        alert = SnmpProvider._format_alert(event)
        assert alert.description == "alternate message field"

    def test_custom_id_preserved(self):
        event = {"oid": "1.3.6.1.6.3.1.1.5.3", "id": "trap-42"}
        alert = SnmpProvider._format_alert(event)
        # AlertDto coerces id to str
        assert alert.id == "trap-42"

    def test_returns_single_alert_dto(self):
        """_format_alert must return AlertDto, not a list, for a single trap."""
        event = {"oid": "1.3.6.1.6.3.1.1.5.4", "host": "router-01"}
        result = SnmpProvider._format_alert(event)
        # Should be a single AlertDto, not a list
        from keep.api.models.alert import AlertDto

        assert isinstance(result, AlertDto)
