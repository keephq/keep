"""
Tests for SNMP Provider - receiving SNMP traps as alerts.
"""

import datetime
import hashlib

import pytest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


class TestFormatAlert:
    """Test _format_alert converts SNMP trap events to AlertDto."""

    def test_full_trap_event(self):
        """Standard SNMP trap with all fields present."""
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.1",
            "community": "public",
            "generic_trap": 2,
            "specific_trap": 0,
            "timestamp": "2024-01-15T10:30:00Z",
            "enterprise": "1.3.6.1.4.1.9",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.2.2.1.1.2", "value": "2", "type": "INTEGER"},
                {"oid": "1.3.6.1.2.1.2.2.1.7.2", "value": "down", "type": "STRING"},
            ],
            "description": "Interface eth0 went down",
            "severity": "high",
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "linkDown"
        assert alert.status == AlertStatus.FIRING.value
        assert alert.severity == AlertSeverity.HIGH.value
        assert "2024-01-15T10:30:00" in alert.lastReceived
        assert alert.description == "Interface eth0 went down"
        assert alert.source == ["snmp"]
        assert alert.trap_oid == "1.3.6.1.6.3.1.1.5.3"
        assert alert.agent_address == "192.168.1.1"
        assert alert.enterprise == "1.3.6.1.4.1.9"
        assert alert.community == "public"
        assert len(alert.varbinds) == 2
        assert alert.labels["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
        assert alert.labels["agent_address"] == "192.168.1.1"

    def test_minimal_trap_event(self):
        """Trap with only the OID - should not raise errors."""
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.1"}

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap 1.3.6.1.6.3.1.1.5.1"
        assert alert.status == AlertStatus.FIRING.value
        assert alert.severity == AlertSeverity.INFO.value
        assert alert.source == ["snmp"]
        assert alert.trap_oid == "1.3.6.1.6.3.1.1.5.1"

    def test_empty_event(self):
        """Empty event should not raise errors."""
        alert = SnmpProvider._format_alert({})

        assert alert.name == "SNMP Trap"
        assert alert.status == AlertStatus.FIRING.value
        assert alert.severity == AlertSeverity.INFO.value
        assert alert.source == ["snmp"]
        assert alert.description == "SNMP Trap received"

    def test_event_with_oid_field(self):
        """Event using 'oid' instead of 'trap_oid'."""
        event = {
            "oid": "1.3.6.1.4.1.2636.4.1.1",
            "agent_address": "10.0.0.1",
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.trap_oid == "1.3.6.1.4.1.2636.4.1.1"
        assert alert.agent_address == "10.0.0.1"

    def test_event_with_source_ip(self):
        """Event using 'source_ip' instead of 'agent_address'."""
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "source_ip": "172.16.0.50",
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.agent_address == "172.16.0.50"

    def test_event_with_variables_field(self):
        """Event using 'variables' instead of 'varbinds'."""
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "variables": [
                {"oid": "1.3.6.1.2.1.1.3.0", "value": "12345", "type": "TimeTicks"},
            ],
        }

        alert = SnmpProvider._format_alert(event)

        assert len(alert.varbinds) == 1
        assert alert.varbinds[0]["oid"] == "1.3.6.1.2.1.1.3.0"

    def test_event_with_custom_name(self):
        """Event with explicit name field."""
        event = {
            "trap_oid": "1.3.6.1.4.1.9.9.43.2.0.1",
            "name": "Cisco Config Change",
            "agent_address": "10.0.0.1",
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "Cisco Config Change"

    def test_event_with_resolved_status(self):
        """Event with resolved status."""
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "agent_address": "192.168.1.1",
            "status": "resolved",
            "description": "Interface eth0 is back up",
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED.value

    def test_event_with_message_as_description(self):
        """Event with 'message' field used as description fallback."""
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "message": "Port 24 link down",
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.description == "Port 24 link down"

    def test_timestamp_defaults_to_now(self):
        """When no timestamp is provided, lastReceived should be set."""
        event = {"trap_oid": "1.3.6.1.6.3.1.1.5.1"}

        alert = SnmpProvider._format_alert(event)

        assert alert.lastReceived is not None
        assert len(alert.lastReceived) > 0

    def test_fingerprint_consistency(self):
        """Same trap_oid and agent_address should produce the same fingerprint."""
        event1 = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.1",
            "timestamp": "2024-01-15T10:30:00Z",
        }
        event2 = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.1",
            "timestamp": "2024-01-15T11:00:00Z",
        }

        alert1 = SnmpProvider._format_alert(event1)
        alert2 = SnmpProvider._format_alert(event2)

        assert alert1.fingerprint == alert2.fingerprint

    def test_fingerprint_differs_for_different_sources(self):
        """Different agent_address should produce different fingerprints."""
        event1 = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.1",
        }
        event2 = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.2",
        }

        alert1 = SnmpProvider._format_alert(event1)
        alert2 = SnmpProvider._format_alert(event2)

        assert alert1.fingerprint != alert2.fingerprint


class TestGetTrapName:
    """Test SNMP trap name resolution."""

    def test_generic_trap_cold_start(self):
        assert SnmpProvider._get_trap_name({"generic_trap": 0}) == "coldStart"

    def test_generic_trap_warm_start(self):
        assert SnmpProvider._get_trap_name({"generic_trap": 1}) == "warmStart"

    def test_generic_trap_link_down(self):
        assert SnmpProvider._get_trap_name({"generic_trap": 2}) == "linkDown"

    def test_generic_trap_link_up(self):
        assert SnmpProvider._get_trap_name({"generic_trap": 3}) == "linkUp"

    def test_generic_trap_auth_failure(self):
        assert (
            SnmpProvider._get_trap_name({"generic_trap": 4})
            == "authenticationFailure"
        )

    def test_generic_trap_egp_neighbor_loss(self):
        assert SnmpProvider._get_trap_name({"generic_trap": 5}) == "egpNeighborLoss"

    def test_generic_trap_enterprise_specific(self):
        assert (
            SnmpProvider._get_trap_name({"generic_trap": 6})
            == "enterpriseSpecific"
        )

    def test_custom_name_takes_precedence(self):
        event = {"generic_trap": 2, "name": "Custom Name"}
        assert SnmpProvider._get_trap_name(event) == "Custom Name"

    def test_trap_oid_as_name(self):
        event = {"trap_oid": "1.3.6.1.4.1.9.9.43.2.0.1"}
        assert SnmpProvider._get_trap_name(event) == "SNMP Trap 1.3.6.1.4.1.9.9.43.2.0.1"

    def test_empty_event_fallback(self):
        assert SnmpProvider._get_trap_name({}) == "SNMP Trap"


class TestGetSeverity:
    """Test severity mapping from SNMP trap data."""

    def test_explicit_critical(self):
        assert SnmpProvider._get_severity({"severity": "critical"}) == AlertSeverity.CRITICAL

    def test_explicit_high(self):
        assert SnmpProvider._get_severity({"severity": "high"}) == AlertSeverity.HIGH

    def test_explicit_warning(self):
        assert SnmpProvider._get_severity({"severity": "warning"}) == AlertSeverity.WARNING

    def test_explicit_info(self):
        assert SnmpProvider._get_severity({"severity": "info"}) == AlertSeverity.INFO

    def test_explicit_low(self):
        assert SnmpProvider._get_severity({"severity": "low"}) == AlertSeverity.LOW

    def test_case_insensitive(self):
        assert SnmpProvider._get_severity({"severity": "CRITICAL"}) == AlertSeverity.CRITICAL
        assert SnmpProvider._get_severity({"severity": "High"}) == AlertSeverity.HIGH

    def test_generic_trap_link_down_severity(self):
        assert SnmpProvider._get_severity({"generic_trap": 2}) == AlertSeverity.HIGH

    def test_generic_trap_cold_start_severity(self):
        assert SnmpProvider._get_severity({"generic_trap": 0}) == AlertSeverity.WARNING

    def test_generic_trap_link_up_severity(self):
        assert SnmpProvider._get_severity({"generic_trap": 3}) == AlertSeverity.INFO

    def test_default_severity(self):
        assert SnmpProvider._get_severity({}) == AlertSeverity.INFO


class TestGetStatus:
    """Test status mapping from SNMP trap data."""

    def test_explicit_firing(self):
        assert SnmpProvider._get_status({"status": "firing"}) == AlertStatus.FIRING

    def test_explicit_resolved(self):
        assert SnmpProvider._get_status({"status": "resolved"}) == AlertStatus.RESOLVED

    def test_explicit_acknowledged(self):
        assert (
            SnmpProvider._get_status({"status": "acknowledged"})
            == AlertStatus.ACKNOWLEDGED
        )

    def test_generic_trap_link_down_fires(self):
        assert SnmpProvider._get_status({"generic_trap": 2}) == AlertStatus.FIRING

    def test_generic_trap_link_up_resolves(self):
        assert SnmpProvider._get_status({"generic_trap": 3}) == AlertStatus.RESOLVED

    def test_generic_trap_auth_failure_fires(self):
        assert SnmpProvider._get_status({"generic_trap": 4}) == AlertStatus.FIRING

    def test_generic_trap_warm_start_resolves(self):
        assert SnmpProvider._get_status({"generic_trap": 1}) == AlertStatus.RESOLVED

    def test_default_status_is_firing(self):
        assert SnmpProvider._get_status({}) == AlertStatus.FIRING


class TestBuildDescription:
    """Test description building from SNMP trap data."""

    def test_explicit_description(self):
        event = {"description": "Interface went down", "trap_oid": "1.3.6.1.6.3.1.1.5.3"}
        assert SnmpProvider._build_description(event) == "Interface went down"

    def test_message_fallback(self):
        event = {"message": "Port 24 link failure"}
        assert SnmpProvider._build_description(event) == "Port 24 link failure"

    def test_auto_generated_from_fields(self):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.1",
        }
        desc = SnmpProvider._build_description(event)
        assert "1.3.6.1.6.3.1.1.5.3" in desc
        assert "192.168.1.1" in desc

    def test_auto_generated_with_varbinds(self):
        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.2.2.1.1.2", "value": "2"},
            ],
        }
        desc = SnmpProvider._build_description(event)
        assert "1.3.6.1.2.1.2.2.1.1.2=2" in desc

    def test_empty_event_default(self):
        assert SnmpProvider._build_description({}) == "SNMP Trap received"

    def test_varbinds_limited_to_five(self):
        event = {
            "varbinds": [
                {"oid": f"1.3.6.1.2.1.{i}", "value": str(i)}
                for i in range(10)
            ],
        }
        desc = SnmpProvider._build_description(event)
        assert "1.3.6.1.2.1.4=4" in desc
        assert "1.3.6.1.2.1.5=5" not in desc


class TestProviderSetup:
    """Test provider initialization and configuration."""

    def _make_provider(self, auth=None):
        context_manager = ContextManager(tenant_id="test", workflow_id="test")
        config = ProviderConfig(
            authentication=auth or {},
            name="test-snmp",
        )
        return SnmpProvider(context_manager, "snmp-test", config)

    def test_no_auth_config(self):
        """Provider should work with empty auth config."""
        provider = self._make_provider()
        assert provider.authentication_config.community_string is None

    def test_with_community_string(self):
        """Provider should accept community string config."""
        provider = self._make_provider({"community_string": "private"})
        assert provider.authentication_config.community_string == "private"

    def test_validate_scopes(self):
        """Validate scopes should always return True for receive_traps."""
        provider = self._make_provider()
        scopes = provider.validate_scopes()
        assert scopes == {"receive_traps": True}

    def test_dispose(self):
        """Dispose should not raise."""
        provider = self._make_provider()
        provider.dispose()

    def test_provider_tags(self):
        assert "alert" in SnmpProvider.PROVIDER_TAGS

    def test_provider_category(self):
        assert "Monitoring" in SnmpProvider.PROVIDER_CATEGORY

    def test_provider_display_name(self):
        assert SnmpProvider.PROVIDER_DISPLAY_NAME == "SNMP"
