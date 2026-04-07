"""
Tests for SNMP provider alert formatting and severity/status extraction.
"""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.snmp_provider.snmp_provider import (
    SnmpProvider,
    _extract_severity,
    _extract_status,
    _build_trap_name,
)


class TestExtractSeverity:
    """Test severity extraction from various payload shapes."""

    def test_explicit_severity_critical(self):
        assert _extract_severity({"severity": "critical"}) == AlertSeverity.CRITICAL

    def test_explicit_severity_warning(self):
        assert _extract_severity({"severity": "warning"}) == AlertSeverity.WARNING

    def test_explicit_severity_info(self):
        assert _extract_severity({"severity": "info"}) == AlertSeverity.INFO

    def test_explicit_severity_case_insensitive(self):
        assert _extract_severity({"severity": "CRITICAL"}) == AlertSeverity.CRITICAL

    def test_explicit_severity_with_whitespace(self):
        assert _extract_severity({"severity": " warning "}) == AlertSeverity.WARNING

    def test_severity_field_capitalized(self):
        assert _extract_severity({"Severity": "error"}) == AlertSeverity.HIGH

    def test_generic_trap_linkdown(self):
        assert _extract_severity({"generic_trap": 2}) == AlertSeverity.HIGH

    def test_generic_trap_linkup(self):
        assert _extract_severity({"generic_trap": 3}) == AlertSeverity.INFO

    def test_generic_trap_coldstart(self):
        assert _extract_severity({"generic_trap": 0}) == AlertSeverity.WARNING

    def test_generic_trap_warmstart(self):
        assert _extract_severity({"generic_trap": 1}) == AlertSeverity.INFO

    def test_generic_trap_auth_failure(self):
        assert _extract_severity({"generic_trap": 4}) == AlertSeverity.WARNING

    def test_generic_trap_egp_loss(self):
        assert _extract_severity({"generic_trap": 5}) == AlertSeverity.WARNING

    def test_generic_trap_enterprise(self):
        assert _extract_severity({"generic_trap": 6}) == AlertSeverity.INFO

    def test_generic_trap_string(self):
        assert _extract_severity({"generic_trap": "2"}) == AlertSeverity.HIGH

    def test_generic_trap_camel_case(self):
        assert _extract_severity({"genericTrap": 2}) == AlertSeverity.HIGH

    def test_keyword_in_description_critical(self):
        assert _extract_severity({"description": "System critical failure"}) == AlertSeverity.CRITICAL

    def test_keyword_in_message_down(self):
        assert _extract_severity({"message": "Link is down"}) == AlertSeverity.HIGH

    def test_keyword_in_msg_degraded(self):
        assert _extract_severity({"msg": "Service degraded"}) == AlertSeverity.WARNING

    def test_keyword_in_trap_description(self):
        assert _extract_severity({"trap_description": "Device is ok"}) == AlertSeverity.INFO

    def test_no_severity_info_defaults(self):
        assert _extract_severity({}) == AlertSeverity.INFO

    def test_explicit_takes_priority_over_generic(self):
        event = {"severity": "critical", "generic_trap": 3}
        assert _extract_severity(event) == AlertSeverity.CRITICAL

    def test_generic_takes_priority_over_keyword(self):
        event = {"generic_trap": 3, "description": "critical error"}
        assert _extract_severity(event) == AlertSeverity.INFO

    def test_invalid_generic_trap_falls_through(self):
        assert _extract_severity({"generic_trap": "invalid"}) == AlertSeverity.INFO


class TestExtractStatus:
    """Test status extraction from various payload shapes."""

    def test_explicit_status_firing(self):
        assert _extract_status({"status": "firing"}) == AlertStatus.FIRING

    def test_explicit_status_resolved(self):
        assert _extract_status({"status": "resolved"}) == AlertStatus.RESOLVED

    def test_explicit_status_ok(self):
        assert _extract_status({"status": "ok"}) == AlertStatus.RESOLVED

    def test_explicit_status_down(self):
        assert _extract_status({"status": "down"}) == AlertStatus.FIRING

    def test_explicit_status_up(self):
        assert _extract_status({"status": "up"}) == AlertStatus.RESOLVED

    def test_explicit_status_clear(self):
        assert _extract_status({"status": "clear"}) == AlertStatus.RESOLVED

    def test_generic_trap_linkdown_firing(self):
        assert _extract_status({"generic_trap": 2}) == AlertStatus.FIRING

    def test_generic_trap_linkup_resolved(self):
        assert _extract_status({"generic_trap": 3}) == AlertStatus.RESOLVED

    def test_generic_trap_warmstart_resolved(self):
        assert _extract_status({"generic_trap": 1}) == AlertStatus.RESOLVED

    def test_generic_trap_coldstart_firing(self):
        assert _extract_status({"generic_trap": 0}) == AlertStatus.FIRING

    def test_no_status_defaults_firing(self):
        assert _extract_status({}) == AlertStatus.FIRING

    def test_explicit_takes_priority(self):
        event = {"status": "resolved", "generic_trap": 0}
        assert _extract_status(event) == AlertStatus.RESOLVED

    def test_invalid_generic_trap(self):
        assert _extract_status({"generic_trap": "bad"}) == AlertStatus.FIRING


class TestBuildTrapName:
    """Test trap name derivation."""

    def test_explicit_name(self):
        assert _build_trap_name({"name": "linkDown"}) == "linkDown"

    def test_trap_oid(self):
        assert _build_trap_name({"trap_oid": "1.3.6.1.6.3.1.1.5.3"}) == "1.3.6.1.6.3.1.1.5.3"

    def test_camel_case_oid(self):
        assert _build_trap_name({"trapOID": "1.3.6.1.4.1.9.0.1"}) == "1.3.6.1.4.1.9.0.1"

    def test_snmp_trap_oid_field(self):
        assert _build_trap_name({"snmpTrapOID": "1.3.6.1.6.3.1.1.5.4"}) == "1.3.6.1.6.3.1.1.5.4"

    def test_generic_trap_names(self):
        assert _build_trap_name({"generic_trap": 0}) == "coldStart"
        assert _build_trap_name({"generic_trap": 1}) == "warmStart"
        assert _build_trap_name({"generic_trap": 2}) == "linkDown"
        assert _build_trap_name({"generic_trap": 3}) == "linkUp"
        assert _build_trap_name({"generic_trap": 4}) == "authenticationFailure"
        assert _build_trap_name({"generic_trap": 5}) == "egpNeighborLoss"
        assert _build_trap_name({"generic_trap": 6}) == "enterpriseSpecific"

    def test_generic_trap_string_input(self):
        assert _build_trap_name({"generic_trap": "2"}) == "linkDown"

    def test_generic_trap_camel_case(self):
        assert _build_trap_name({"genericTrap": 3}) == "linkUp"

    def test_unknown_generic_trap(self):
        assert _build_trap_name({"generic_trap": 99}) == "genericTrap(99)"

    def test_empty_event_default_name(self):
        assert _build_trap_name({}) == "SNMP Trap"

    def test_name_takes_priority(self):
        event = {"name": "myTrap", "trap_oid": "1.2.3", "generic_trap": 0}
        assert _build_trap_name(event) == "myTrap"


class TestFormatAlert:
    """Test the full _format_alert pipeline."""

    def test_linkdown_trap(self):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "generic_trap": 2,
            "agent_address": "192.168.1.1",
            "community": "public",
            "description": "Interface eth0 is down",
            "varbinds": {"1.3.6.1.2.1.2.2.1.1": "2"},
            "timestamp": "2025-01-15T10:30:00Z",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "1.3.6.1.6.3.1.1.5.3"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING
        assert alert.agent_address == "192.168.1.1"
        assert alert.community == "public"
        assert alert.description == "Interface eth0 is down"
        assert alert.source == ["snmp"]
        assert alert.lastReceived == "2025-01-15T10:30:00Z"

    def test_linkup_resolved(self):
        event = {
            "generic_trap": 3,
            "agent_address": "10.0.0.1",
            "description": "Interface back up",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "linkUp"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_explicit_severity_and_status(self):
        event = {
            "name": "diskUsageHigh",
            "severity": "critical",
            "status": "firing",
            "agent_address": "10.0.0.5",
            "description": "Disk usage above 95%",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "diskUsageHigh"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

    def test_empty_event(self):
        alert = SnmpProvider._format_alert({})
        assert alert.name == "SNMP Trap"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING
        assert alert.source == ["snmp"]

    def test_numeric_timestamp(self):
        event = {
            "trap_oid": "1.3.6.1.4.1.9.0.1",
            "timestamp": 1705312200,
            "agent_address": "10.0.0.1",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.lastReceived is not None
        assert "2024" in alert.lastReceived  # Jan 15 2024

    def test_batch_payload_takes_first(self):
        events = [
            {"name": "firstTrap", "agent_address": "10.0.0.1"},
            {"name": "secondTrap", "agent_address": "10.0.0.2"},
        ]
        alert = SnmpProvider._format_alert(events)
        assert alert.name == "firstTrap"

    def test_batch_empty_list(self):
        alert = SnmpProvider._format_alert([])
        assert alert.name == "SNMP Trap"

    def test_camel_case_fields(self):
        event = {
            "trapOID": "1.3.6.1.6.3.1.1.5.4",
            "genericTrap": 3,
            "agentAddress": "192.168.0.10",
            "trapDescription": "link is up",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.trap_oid == "1.3.6.1.6.3.1.1.5.4"
        assert alert.agent_address == "192.168.0.10"
        assert alert.name == "1.3.6.1.6.3.1.1.5.4"

    def test_enterprise_and_specific_trap(self):
        event = {
            "generic_trap": 6,
            "specific_trap": 42,
            "enterprise": "1.3.6.1.4.1.9",
            "agent_address": "10.1.1.1",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.enterprise == "1.3.6.1.4.1.9"
        assert alert.specific_trap == 42
        assert alert.generic_trap == 6

    def test_varbinds_preserved(self):
        vb = {"1.3.6.1.2.1.1.3.0": "123456", "1.3.6.1.2.1.1.5.0": "router01"}
        event = {"trap_oid": "1.2.3", "varbinds": vb}
        alert = SnmpProvider._format_alert(event)
        assert alert.varbinds == vb

    def test_id_constructed_from_oid_and_agent(self):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "10.0.0.1",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.id == "1.3.6.1.6.3.1.1.5.3:10.0.0.1"

    def test_explicit_id_used(self):
        event = {
            "id": "my-custom-id-123",
            "trap_oid": "1.2.3",
            "agent_address": "10.0.0.1",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.id == "my-custom-id-123"

    def test_alternative_source_fields(self):
        event = {"sourceIP": "172.16.0.1"}
        alert = SnmpProvider._format_alert(event)
        assert alert.agent_address == "172.16.0.1"

    def test_status_resolved_with_clear(self):
        event = {"status": "clear", "name": "tempCheck"}
        alert = SnmpProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_message_as_description(self):
        event = {"message": "CPU usage high on router01"}
        alert = SnmpProvider._format_alert(event)
        assert alert.description == "CPU usage high on router01"

    def test_msg_as_description(self):
        event = {"msg": "Memory threshold exceeded"}
        alert = SnmpProvider._format_alert(event)
        assert alert.description == "Memory threshold exceeded"

    def test_full_snmptt_style_payload(self):
        """Simulate a payload from snmptt with typical fields."""
        event = {
            "trap_oid": "1.3.6.1.4.1.2021.13.15.1.3.1",
            "agent_address": "192.168.10.50",
            "community": "monitoring",
            "generic_trap": 6,
            "specific_trap": 1,
            "enterprise": "1.3.6.1.4.1.2021",
            "severity": "warning",
            "description": "Disk /dev/sda1 usage at 85%",
            "varbinds": {
                "1.3.6.1.4.1.2021.9.1.2.1": "/dev/sda1",
                "1.3.6.1.4.1.2021.9.1.9.1": "85",
            },
            "timestamp": "2025-06-01T14:00:00Z",
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.name == "1.3.6.1.4.1.2021.13.15.1.3.1"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
        assert alert.agent_address == "192.168.10.50"
        assert alert.community == "monitoring"
        assert alert.enterprise == "1.3.6.1.4.1.2021"
        assert alert.specific_trap == 1
        assert alert.generic_trap == 6
        assert alert.description == "Disk /dev/sda1 usage at 85%"
        assert len(alert.varbinds) == 2
        assert alert.source == ["snmp"]
