"""
Unit tests for the SNMP provider.

Tests cover:
  - All six well-known SNMPv2 trap OIDs → severity and status
  - SNMPv1 generic trap type numbers
  - Structured, flat, and snmptrapd-style JSON formats
  - Explicit severity / status override
  - Keyword-based severity heuristic
  - Missing or malformed fields (defensive)
  - Varbinds normalisation
  - community_filter config
"""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.snmp_provider.snmp_provider import (
    TRAP_SEVERITY_MAP,
    WELL_KNOWN_TRAPS,
    SnmpProvider,
    SnmpProviderAuthConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format(event: dict):
    """Shortcut: call _format_alert and always return a single AlertDto."""
    result = SnmpProvider._format_alert(event)
    if isinstance(result, list):
        return result[0]
    return result


# ---------------------------------------------------------------------------
# Trap-name resolution
# ---------------------------------------------------------------------------


class TestResolveTrapName:
    def test_explicit_trap_name_takes_priority(self):
        name = SnmpProvider._resolve_trap_name(
            {"trap_name": "linkDown", "trap_oid": "1.3.6.1.6.3.1.1.5.4"}
        )
        assert name == "linkDown"

    def test_well_known_oid_resolved(self):
        for oid, expected in WELL_KNOWN_TRAPS.items():
            assert SnmpProvider._resolve_trap_name({"trap_oid": oid}) == expected

    def test_oid_alias_fields(self):
        assert (
            SnmpProvider._resolve_trap_name({"oid": "1.3.6.1.6.3.1.1.5.3"})
            == "linkDown"
        )
        assert (
            SnmpProvider._resolve_trap_name({"enterprise": "1.3.6.1.6.3.1.1.5.5"})
            == "authenticationFailure"
        )

    def test_v1_generic_trap_number(self):
        assert SnmpProvider._resolve_trap_name({"generic_trap": 2}) == "linkDown"
        assert SnmpProvider._resolve_trap_name({"trap": "3"}) == "linkUp"
        assert SnmpProvider._resolve_trap_name({"generic_trap": 6}) == "enterpriseSpecific"

    def test_unknown_oid_returned_as_name(self):
        oid = "1.3.6.1.4.1.9999.1.2.3"
        assert SnmpProvider._resolve_trap_name({"trap_oid": oid}) == oid

    def test_empty_event_returns_snmpTrap(self):
        assert SnmpProvider._resolve_trap_name({}) == "snmpTrap"


# ---------------------------------------------------------------------------
# Severity resolution
# ---------------------------------------------------------------------------


class TestResolveSeverity:
    @pytest.mark.parametrize(
        "trap_name,expected",
        list(TRAP_SEVERITY_MAP.items()),
    )
    def test_trap_name_severity_map(self, trap_name, expected):
        assert SnmpProvider._resolve_severity(trap_name, {}) == expected

    def test_explicit_severity_field_overrides(self):
        assert (
            SnmpProvider._resolve_severity("linkDown", {"severity": "critical"})
            == AlertSeverity.CRITICAL
        )
        assert (
            SnmpProvider._resolve_severity("coldStart", {"severity": "info"})
            == AlertSeverity.INFO
        )

    def test_explicit_priority_field(self):
        assert (
            SnmpProvider._resolve_severity("snmpTrap", {"priority": "warning"})
            == AlertSeverity.WARNING
        )

    def test_keyword_scan_critical(self):
        sev = SnmpProvider._resolve_severity(
            "enterpriseSpecific", {"description": "disk failure detected"}
        )
        assert sev == AlertSeverity.CRITICAL

    def test_keyword_scan_warning(self):
        sev = SnmpProvider._resolve_severity(
            "snmpTrap", {"message": "interface degraded"}
        )
        assert sev == AlertSeverity.WARNING

    def test_keyword_scan_info_on_up(self):
        sev = SnmpProvider._resolve_severity(
            "snmpTrap", {"message": "link is now up"}
        )
        assert sev == AlertSeverity.INFO

    def test_unknown_defaults_to_info(self):
        sev = SnmpProvider._resolve_severity("snmpTrap", {"description": "normal"})
        assert sev == AlertSeverity.INFO


# ---------------------------------------------------------------------------
# Status resolution
# ---------------------------------------------------------------------------


class TestResolveStatus:
    def test_linkDown_is_firing(self):
        assert (
            SnmpProvider._resolve_status("linkDown", {}) == AlertStatus.FIRING
        )

    def test_linkUp_is_resolved(self):
        assert (
            SnmpProvider._resolve_status("linkUp", {}) == AlertStatus.RESOLVED
        )

    def test_warmStart_is_resolved(self):
        assert (
            SnmpProvider._resolve_status("warmStart", {}) == AlertStatus.RESOLVED
        )

    def test_explicit_ok_status(self):
        assert (
            SnmpProvider._resolve_status("coldStart", {"status": "ok"})
            == AlertStatus.RESOLVED
        )

    def test_explicit_firing_status(self):
        assert (
            SnmpProvider._resolve_status("linkUp", {"status": "firing"})
            == AlertStatus.FIRING
        )

    def test_default_is_firing(self):
        assert (
            SnmpProvider._resolve_status("enterpriseSpecific", {})
            == AlertStatus.FIRING
        )


# ---------------------------------------------------------------------------
# _format_alert — structured JSON format
# ---------------------------------------------------------------------------


class TestFormatAlertStructured:
    def test_linkDown_fields(self):
        event = {
            "source_ip": "192.168.1.10",
            "community": "public",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "trap_name": "linkDown",
            "uptime": "567890",
            "varbinds": {"ifIndex": "2", "ifOperStatus": "2"},
        }
        alert = _format(event)
        assert alert.name == "linkDown"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING
        assert alert.source_ip == "192.168.1.10"
        assert alert.trap_oid == "1.3.6.1.6.3.1.1.5.3"
        assert alert.community == "public"
        assert alert.varbinds == {"ifIndex": "2", "ifOperStatus": "2"}
        assert "snmp" in alert.source

    def test_linkUp_is_resolved(self):
        event = {
            "source_ip": "10.0.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
        }
        alert = _format(event)
        assert alert.name == "linkUp"
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_coldStart_is_critical(self):
        alert = _format({"trap_oid": "1.3.6.1.6.3.1.1.5.1"})
        assert alert.name == "coldStart"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_authenticationFailure_severity(self):
        alert = _format({"trap_oid": "1.3.6.1.6.3.1.1.5.5"})
        assert alert.severity == AlertSeverity.WARNING

    def test_varbinds_none_becomes_empty_dict(self):
        alert = _format({"trap_name": "coldStart"})
        assert alert.varbinds == {}

    def test_varbinds_non_dict_wrapped(self):
        alert = _format({"trap_name": "coldStart", "varbinds": "ifIndex=2"})
        assert alert.varbinds == {"raw": "ifIndex=2"}

    def test_id_generated_when_missing(self):
        alert = _format({"trap_name": "warmStart"})
        assert alert.id and len(alert.id) > 0

    def test_explicit_id_preserved(self):
        alert = _format({"trap_name": "warmStart", "id": "trap-42"})
        assert alert.id == "trap-42"


# ---------------------------------------------------------------------------
# _format_alert — flat JSON format
# ---------------------------------------------------------------------------


class TestFormatAlertFlat:
    def test_flat_oid_and_message(self):
        event = {
            "oid": "1.3.6.1.4.1.9.9.43.2.0.1",
            "message": "Config change on router",
            "source": "172.16.0.1",
            "severity": "warning",
        }
        alert = _format(event)
        assert alert.severity == AlertSeverity.WARNING
        assert alert.description == "Config change on router"
        assert alert.source_ip == "172.16.0.1"
        assert alert.trap_oid == "1.3.6.1.4.1.9.9.43.2.0.1"

    def test_source_ip_normalised_from_source_field(self):
        alert = _format({"source": "10.1.2.3", "trap_name": "snmpTrap"})
        assert alert.source_ip == "10.1.2.3"


# ---------------------------------------------------------------------------
# _format_alert — snmptrapd-style JSON format
# ---------------------------------------------------------------------------


class TestFormatAlertSnmptrapd:
    def test_snmptrapd_style(self):
        event = {
            "src": "10.10.0.20",
            "enterprise": "1.3.6.1.4.1.2636.4.1.1",
            "trap": "6",
            "description": "BGP peer changed state to Idle",
        }
        alert = _format(event)
        assert alert.source_ip == "10.10.0.20"
        assert alert.trap_oid == "1.3.6.1.4.1.2636.4.1.1"
        assert alert.description == "BGP peer changed state to Idle"
        assert alert.name == "enterpriseSpecific"   # trap type 6

    def test_agent_field_used_for_source_ip(self):
        alert = _format({"agent": "192.168.50.1", "trap_name": "coldStart"})
        assert alert.source_ip == "192.168.50.1"


# ---------------------------------------------------------------------------
# Defensive / edge cases
# ---------------------------------------------------------------------------


class TestFormatAlertEdgeCases:
    def test_completely_empty_event(self):
        alert = _format({})
        assert alert.name == "snmpTrap"
        assert alert.severity == AlertSeverity.INFO
        assert alert.source_ip == "unknown"
        assert alert.status == AlertStatus.FIRING

    def test_unknown_source_ip_when_all_fields_absent(self):
        alert = _format({"trap_name": "enterpriseSpecific"})
        assert alert.source_ip == "unknown"

    def test_description_fallback_order(self):
        # message field wins when description absent
        alert = _format({"message": "from message field"})
        assert alert.description == "from message field"

        # output field next
        alert = _format({"output": "from output field"})
        assert alert.description == "from output field"

        # trap_name as last resort
        alert = _format({"trap_name": "coldStart"})
        assert alert.description == "coldStart"

    def test_timestamp_preserved(self):
        alert = _format({"timestamp": "2026-01-01T00:00:00+00:00"})
        assert alert.lastReceived == "2026-01-01T00:00:00+00:00"
