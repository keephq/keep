"""Tests for the SNMP provider."""

import datetime
import json

import pytest

from keep.providers.snmp_provider.snmp_provider import (
    WELL_KNOWN_TRAPS,
    SnmpProvider,
)


class TestParseEventRawBody:
    def test_dict_passthrough(self):
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.3", "source_ip": "10.0.0.1"}
        result = SnmpProvider.parse_event_raw_body(event)
        assert result == event

    def test_bytes_json(self):
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        raw = json.dumps(event).encode()
        result = SnmpProvider.parse_event_raw_body(raw)
        assert result["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"

    def test_bytes_invalid_json(self):
        raw = b"not json at all"
        result = SnmpProvider.parse_event_raw_body(raw)
        assert "raw" in result
        assert result["raw"] == "not json at all"

    def test_other_type(self):
        result = SnmpProvider.parse_event_raw_body(12345)
        assert "raw" in result


class TestGetTrapName:
    def test_well_known_cold_start(self):
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.1"}
        assert SnmpProvider._get_trap_name(event) == "coldStart"

    def test_well_known_link_down(self):
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        assert SnmpProvider._get_trap_name(event) == "linkDown"

    def test_well_known_link_up(self):
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.4"}
        assert SnmpProvider._get_trap_name(event) == "linkUp"

    def test_well_known_auth_failure(self):
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.5"}
        assert SnmpProvider._get_trap_name(event) == "authenticationFailure"

    def test_generic_trap_v1_linkdown(self):
        event = {"generic_trap": 2}
        assert SnmpProvider._get_trap_name(event) == "linkDown"

    def test_generic_trap_v1_string(self):
        event = {"generic_trap": "0"}
        assert SnmpProvider._get_trap_name(event) == "coldStart"

    def test_enterprise_specific_oid(self):
        event = {"trap_oid": "1.3.6.1.4.1.8072.2.3.0.1"}
        assert SnmpProvider._get_trap_name(event) == "trap:1.3.6.1.4.1.8072.2.3.0.1"

    def test_unknown_trap(self):
        event = {}
        assert SnmpProvider._get_trap_name(event) == "Unknown SNMP Trap"


class TestGetSeverity:
    def test_link_down_critical(self):
        from keep.api.models.alert import AlertSeverity
        assert SnmpProvider._get_severity("linkDown", {}) == AlertSeverity.CRITICAL

    def test_cold_start_info(self):
        from keep.api.models.alert import AlertSeverity
        assert SnmpProvider._get_severity("coldStart", {}) == AlertSeverity.INFO

    def test_auth_failure_warning(self):
        from keep.api.models.alert import AlertSeverity
        assert SnmpProvider._get_severity("authenticationFailure", {}) == AlertSeverity.WARNING

    def test_enterprise_specific_default_warning(self):
        from keep.api.models.alert import AlertSeverity
        assert SnmpProvider._get_severity("trap:1.3.6.1.4.1.999", {}) == AlertSeverity.WARNING

    def test_event_provided_severity(self):
        from keep.api.models.alert import AlertSeverity
        assert SnmpProvider._get_severity("trap:custom", {"severity": "critical"}) == AlertSeverity.CRITICAL


class TestGetStatus:
    def test_link_up_resolved(self):
        from keep.api.models.alert import AlertStatus
        assert SnmpProvider._get_status("linkUp") == AlertStatus.RESOLVED

    def test_link_down_firing(self):
        from keep.api.models.alert import AlertStatus
        assert SnmpProvider._get_status("linkDown") == AlertStatus.FIRING

    def test_unknown_firing(self):
        from keep.api.models.alert import AlertStatus
        assert SnmpProvider._get_status("trap:custom") == AlertStatus.FIRING


class TestBuildFingerprint:
    def test_same_input_same_fingerprint(self):
        event = {"source_ip": "10.0.0.1", "trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        fp1 = SnmpProvider._build_fingerprint(event, "linkDown")
        fp2 = SnmpProvider._build_fingerprint(event, "linkDown")
        assert fp1 == fp2

    def test_different_source_different_fingerprint(self):
        event1 = {"source_ip": "10.0.0.1", "trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        event2 = {"source_ip": "10.0.0.2", "trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        fp1 = SnmpProvider._build_fingerprint(event1, "linkDown")
        fp2 = SnmpProvider._build_fingerprint(event2, "linkDown")
        assert fp1 != fp2

    def test_different_trap_different_fingerprint(self):
        event1 = {"source_ip": "10.0.0.1", "trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        event2 = {"source_ip": "10.0.0.1", "trap_oid": "1.3.6.1.6.3.1.1.5.4"}
        fp1 = SnmpProvider._build_fingerprint(event1, "linkDown")
        fp2 = SnmpProvider._build_fingerprint(event2, "linkUp")
        assert fp1 != fp2


class TestFormatAlert:
    def _make_v2c_linkdown_event(self):
        return {
            "version": "2c",
            "community": "public",
            "source_ip": "192.168.1.1",
            "source_port": 162,
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "timestamp": "2026-02-15T12:00:00Z",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.1.3.0", "type": "TimeTicks", "value": "12345"},
                {"oid": "1.3.6.1.2.1.2.2.1.1.2", "type": "Integer", "value": "2"},
            ],
        }

    def _make_v1_coldstart_event(self):
        return {
            "version": "1",
            "community": "private",
            "source_ip": "10.0.0.5",
            "enterprise": "1.3.6.1.4.1.8072",
            "agent_address": "10.0.0.5",
            "generic_trap": 0,
            "specific_trap": 0,
            "timestamp": "2026-02-15T08:00:00Z",
            "varbinds": [],
        }

    def _make_enterprise_event(self):
        return {
            "version": "2c",
            "community": "monitoring",
            "source_ip": "172.16.0.100",
            "trap_oid": "1.3.6.1.4.1.8072.2.3.0.1",
            "timestamp": "2026-02-15T14:30:00Z",
            "varbinds": [
                {"oid": "1.3.6.1.4.1.8072.2.3.2.1", "type": "OctetString", "value": "Disk full"},
            ],
        }

    def test_v2c_linkdown(self):
        event = self._make_v2c_linkdown_event()
        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap: linkDown"
        assert alert.severity.name == "CRITICAL"
        assert alert.status.value == "firing"
        assert alert.source == ["snmp"]
        assert alert.pushed is True
        assert alert.labels["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
        assert alert.labels["source_ip"] == "192.168.1.1"
        assert alert.labels["snmp_version"] == "2c"
        assert alert.labels["community"] == "public"
        assert "varbind:1.3.6.1.2.1.1.3.0" in alert.labels
        assert alert.fingerprint is not None
        assert len(alert.fingerprint) == 64  # SHA256 hex

    def test_v1_coldstart(self):
        event = self._make_v1_coldstart_event()
        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap: coldStart"
        assert alert.severity.name == "INFO"
        assert alert.status.value == "firing"
        assert alert.labels["enterprise"] == "1.3.6.1.4.1.8072"

    def test_linkup_resolved(self):
        event = {
            "version": "2c",
            "source_ip": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "timestamp": "2026-02-15T12:05:00Z",
            "varbinds": [],
        }
        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap: linkUp"
        assert alert.status.value == "resolved"
        assert alert.severity.name == "INFO"

    def test_enterprise_specific_trap(self):
        event = self._make_enterprise_event()
        alert = SnmpProvider._format_alert(event)

        assert "trap:" in alert.name
        assert alert.severity.name == "WARNING"
        assert alert.status.value == "firing"
        assert "varbind:1.3.6.1.4.1.8072.2.3.2.1" in alert.labels
        assert alert.labels["varbind:1.3.6.1.4.1.8072.2.3.2.1"] == "Disk full"

    def test_description_includes_source(self):
        event = self._make_v2c_linkdown_event()
        alert = SnmpProvider._format_alert(event)

        assert "192.168.1.1" in alert.description
        assert "linkDown" in alert.description
        assert "SNMPv2c" in alert.description

    def test_minimal_event(self):
        """Provider should handle a minimal event without crashing."""
        event = {}
        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap: Unknown SNMP Trap"
        assert alert.source == ["snmp"]
        assert alert.fingerprint is not None

    def test_varbinds_in_description(self):
        event = self._make_v2c_linkdown_event()
        alert = SnmpProvider._format_alert(event)

        assert "Variable bindings (2)" in alert.description
        assert "1.3.6.1.2.1.1.3.0" in alert.description

    def test_hostname_set_to_source_ip(self):
        event = self._make_v2c_linkdown_event()
        alert = SnmpProvider._format_alert(event)

        assert alert.hostname == "192.168.1.1"
        assert alert.service == "192.168.1.1"

    def test_auth_failure(self):
        event = {
            "version": "2c",
            "source_ip": "10.0.0.99",
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "timestamp": "2026-02-15T16:00:00Z",
            "varbinds": [],
        }
        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap: authenticationFailure"
        assert alert.severity.name == "WARNING"
        assert alert.status.value == "firing"
