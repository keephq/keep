"""Tests for the SNMP Provider."""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


class TestSnmpFormatAlert:
    """Test _format_alert static method."""

    def test_linkdown_trap_v2c(self):
        event = {
            "host": "router1.example.com",
            "source_ip": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "generic_trap": 2,
            "version": "v2c",
            "message": "Interface GigabitEthernet0/1 went down",
            "timestamp": "2026-03-01T10:30:00Z",
            "variables": {"1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1"},
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "linkDown"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.host == "router1.example.com"
        assert alert.source == ["snmp"]
        assert alert.pushed is True

    def test_linkup_trap_resolves(self):
        event = {
            "host": "switch1.example.com",
            "source_ip": "10.0.0.5",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "message": "Interface came back up",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "linkUp"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_auth_failure_trap(self):
        event = {
            "host": "firewall.example.com",
            "source_ip": "172.16.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "message": "SNMP authentication failure",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "authenticationFailure"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_cold_start_trap(self):
        event = {
            "source_ip": "10.10.10.100",
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "message": "Agent restarted",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "coldStart"
        assert alert.severity == AlertSeverity.INFO

    def test_generic_trap_integer_fallback(self):
        """When trap_oid is not in the well-known table, fall back to generic_trap int."""
        event = {
            "host": "device.example.com",
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.4.1.9999.0.1",
            "generic_trap": 2,
            "message": "Link down via generic trap",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

    def test_enterprise_specific_trap(self):
        """Enterprise-specific trap (generic_trap=6) with explicit severity."""
        event = {
            "host": "ups.example.com",
            "source_ip": "192.168.5.10",
            "trap_oid": "1.3.6.1.4.1.318.0.5",
            "enterprise": "1.3.6.1.4.1.318",
            "generic_trap": 6,
            "specific_trap": 5,
            "severity": "critical",
            "message": "UPS on battery power",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL
        assert "UPS on battery power" in alert.message

    def test_explicit_severity_overrides_trap_default(self):
        """An explicit severity field should override the well-known trap default."""
        event = {
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",  # coldStart = INFO by default
            "severity": "warning",
            "message": "Cold start with custom severity",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING

    def test_explicit_status_resolved(self):
        event = {
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",  # linkDown = FIRING by default
            "status": "resolved",
            "message": "Manually resolved",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_unknown_trap_oid_uses_oid_as_name(self):
        event = {
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.4.1.12345.0.99",
            "message": "Unknown enterprise trap",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "snmpTrap:1.3.6.1.4.1.12345.0.99"
        assert alert.severity == AlertSeverity.INFO

    def test_minimal_event(self):
        """Minimal event with almost no fields should still produce a valid alert."""
        event = {"source_ip": "10.0.0.1"}
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "SNMP Trap"
        assert alert.source == ["snmp"]
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING

    def test_fingerprint_deduplication(self):
        """Same trap_oid + source_ip + enterprise should produce the same fingerprint."""
        event1 = {
            "source_ip": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "enterprise": "1.3.6.1.4.1.9",
            "message": "First occurrence",
        }
        event2 = {
            "source_ip": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "enterprise": "1.3.6.1.4.1.9",
            "message": "Second occurrence",
        }
        alert1 = SnmpProvider._format_alert(event1)
        alert2 = SnmpProvider._format_alert(event2)
        assert alert1.fingerprint == alert2.fingerprint

    def test_different_sources_different_fingerprints(self):
        event1 = {
            "source_ip": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "message": "From device A",
        }
        event2 = {
            "source_ip": "192.168.1.2",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "message": "From device B",
        }
        alert1 = SnmpProvider._format_alert(event1)
        alert2 = SnmpProvider._format_alert(event2)
        assert alert1.fingerprint != alert2.fingerprint

    def test_auto_generated_message(self):
        """When no message is provided, one should be auto-generated."""
        event = {
            "host": "mydevice.local",
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "enterprise": "1.3.6.1.4.1.9",
            "variables": {"1.3.6.1.2.1.2.2.1.2": "Gi0/1"},
        }
        alert = SnmpProvider._format_alert(event)
        assert "linkDown" in alert.message
        assert "mydevice.local" in alert.message

    def test_host_defaults_to_source_ip(self):
        event = {
            "source_ip": "10.0.0.99",
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "message": "Test",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.host == "10.0.0.99"

    def test_snmp_extra_fields_preserved(self):
        """SNMP-specific fields should be stored on the alert via Extra.allow."""
        event = {
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "version": "v2c",
            "community": "public",
            "enterprise": "1.3.6.1.4.1.9",
            "variables": {"1.3.6.1.2.1.2.2.1.2": "Gi0/1"},
            "message": "Test",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.trap_oid == "1.3.6.1.6.3.1.1.5.3"
        assert alert.snmp_version == "v2c"
        assert alert.community == "public"
        assert alert.variables == {"1.3.6.1.2.1.2.2.1.2": "Gi0/1"}
