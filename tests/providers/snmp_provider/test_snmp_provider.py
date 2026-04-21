"""Tests for SNMP webhook provider."""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


class TestResolveTrapName:
    def test_explicit_trap_name_snake_case(self):
        event = {"trap_name": "linkDown", "trap_type": 2}
        assert SnmpProvider._resolve_trap_name(event) == "linkDown"

    def test_explicit_trap_name_camel_case(self):
        event = {"trapName": "authenticationFailure"}
        assert SnmpProvider._resolve_trap_name(event) == "authenticationFailure"

    def test_numeric_trap_type_resolves_to_name(self):
        for trap_type, expected in SnmpProvider.GENERIC_TRAP_NAMES.items():
            assert SnmpProvider._resolve_trap_name({"trap_type": trap_type}) == expected

    def test_camel_case_trap_type(self):
        assert SnmpProvider._resolve_trap_name({"trapType": 3}) == "linkUp"

    def test_unknown_trap_type_falls_back_to_enterprise_specific(self):
        assert SnmpProvider._resolve_trap_name({"trap_type": 99}) == "enterpriseSpecific"

    def test_missing_fields_defaults_to_enterprise_specific(self):
        assert SnmpProvider._resolve_trap_name({}) == "enterpriseSpecific"


class TestFormatVarbinds:
    def test_dict_varbinds_with_type(self):
        varbinds = [{"oid": "1.3.6.1.2.1.2.2.1.1.1", "type": "integer", "value": "1"}]
        result = SnmpProvider._format_varbinds(varbinds)
        assert "1.3.6.1.2.1.2.2.1.1.1" in result
        assert "integer" in result
        assert "1" in result

    def test_dict_varbinds_without_type(self):
        varbinds = [{"oid": "ifDescr", "value": "eth0"}]
        result = SnmpProvider._format_varbinds(varbinds)
        assert "ifDescr: eth0" in result

    def test_multiple_varbinds(self):
        varbinds = [
            {"oid": "oid1", "type": "integer", "value": "1"},
            {"oid": "oid2", "type": "octet-string", "value": "eth0"},
        ]
        result = SnmpProvider._format_varbinds(varbinds)
        assert result.count("\n") == 1

    def test_empty_varbinds_returns_none(self):
        assert SnmpProvider._format_varbinds([]) is None
        assert SnmpProvider._format_varbinds(None) is None

    def test_non_dict_varbind(self):
        result = SnmpProvider._format_varbinds(["raw varbind"])
        assert result == "raw varbind"


class TestFormatAlert:
    def _linkdown_event(self):
        return {
            "agent_addr": "192.168.1.10",
            "trap_type": 2,
            "trap_name": "linkDown",
            "enterprise": "1.3.6.1.2.1.11",
            "uptime": "123456",
            "timestamp": "2024-10-26T23:20:39+00:00",
            "community": "public",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.2.2.1.1.1", "type": "integer", "value": "1"},
                {"oid": "1.3.6.1.2.1.2.2.1.2.1", "type": "octet-string", "value": "eth0"},
            ],
        }

    def test_linkdown_severity_and_status(self):
        alert = SnmpProvider._format_alert(self._linkdown_event())
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

    def test_linkup_resolves(self):
        event = {"trap_type": 3, "agent_addr": "10.0.0.1"}
        alert = SnmpProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_cold_start_fires(self):
        alert = SnmpProvider._format_alert({"trap_type": 0})
        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.WARNING

    def test_authentication_failure_severity(self):
        alert = SnmpProvider._format_alert({"trap_type": 4})
        assert alert.severity == AlertSeverity.HIGH

    def test_name_includes_agent_addr(self):
        alert = SnmpProvider._format_alert(self._linkdown_event())
        assert "192.168.1.10" in alert.name
        assert "linkDown" in alert.name

    def test_name_without_agent_addr(self):
        alert = SnmpProvider._format_alert({"trap_type": 2, "trap_name": "linkDown"})
        assert "linkDown" in alert.name

    def test_source_is_snmp(self):
        alert = SnmpProvider._format_alert(self._linkdown_event())
        assert alert.source == ["snmp"]

    def test_varbinds_in_description(self):
        alert = SnmpProvider._format_alert(self._linkdown_event())
        assert "eth0" in alert.description

    def test_camel_case_fields_accepted(self):
        event = {
            "agentAddr": "10.0.0.5",
            "trapType": 2,
            "trapName": "linkDown",
            "enterpriseOid": "1.3.6.1.4.1.9",
            "variableBindings": [{"oid": "ifIndex", "value": "2"}],
        }
        alert = SnmpProvider._format_alert(event)
        assert alert.agent_addr == "10.0.0.5"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_enterprise_specific_defaults_to_info(self):
        alert = SnmpProvider._format_alert({"trap_type": 6})
        assert alert.severity == AlertSeverity.INFO

    def test_missing_timestamp_defaults_to_now(self):
        alert = SnmpProvider._format_alert({"trap_type": 0})
        assert alert.lastReceived is not None

    def test_alert_id_from_event(self):
        alert = SnmpProvider._format_alert({"trap_id": "abc123", "trap_type": 0})
        assert alert.id == "abc123"

    def test_completely_empty_event(self):
        alert = SnmpProvider._format_alert({})
        assert alert.source == ["snmp"]
        assert alert.trap_name == "enterpriseSpecific"

    def test_egp_neighbor_loss_severity(self):
        alert = SnmpProvider._format_alert({"trap_type": 5})
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
