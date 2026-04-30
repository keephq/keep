"""
Tests for SNMP Provider
"""

import pytest
from unittest.mock import MagicMock

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.providers.models.provider_config import ProviderConfig


@pytest.fixture
def snmp_provider():
    """Create SNMP provider instance for testing."""
    context_manager = MagicMock(spec=ContextManager)
    config = ProviderConfig(
        authentication={"community": "public"},
    )
    provider = SnmpProvider(context_manager, "snmp-test", config)
    provider.authentication_config = provider.SnmpProviderAuthConfig(community="public")
    return provider


class TestSnmpProvider:
    """Test SNMP provider functionality."""

    def test_parse_basic_trap(self, snmp_provider):
        """Test parsing a basic SNMP trap."""
        event = {
            "version": "v2c",
            "community": "public",
            "enterprise": "1.3.6.1.4.1.8072.2.3",
            "agentAddress": "192.168.1.100",
            "trapType": "enterpriseSpecific",
            "specificTrap": 1,
            "uptime": "123456789",
        }

        alert = snmp_provider.format_alert(event)

        assert alert.name == "SNMP Trap - 2.3"
        assert alert.snmpSource == "192.168.1.100"
        assert alert.snmpOid == "1.3.6.1.4.1.8072.2.3"
        assert alert.snmpVersion == "v2c"
        assert alert.status == AlertStatus.FIRING

    def test_parse_link_down_trap(self, snmp_provider):
        """Test parsing linkDown trap."""
        event = {
            "version": "v1",
            "trapType": "linkDown",
            "agentAddress": "10.0.0.1",
            "uptime": "3600",
        }

        alert = snmp_provider.format_alert(event)

        assert "linkDown" in alert.name or "link Down" in alert.name.lower()
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

    def test_parse_link_up_trap(self, snmp_provider):
        """Test parsing linkUp trap (resolved)."""
        event = {
            "version": "v1",
            "trapType": "linkUp",
            "agentAddress": "10.0.0.1",
            "uptime": "3600",
        }

        alert = snmp_provider.format_alert(event)

        assert alert.status == AlertStatus.RESOLVED

    def test_parse_trap_with_varbinds(self, snmp_provider):
        """Test parsing trap with variable bindings."""
        event = {
            "version": "v2c",
            "oid": "1.3.6.1.4.1.9.9.43.2.0.1",
            "source": "192.168.1.1",
            "varbinds": {
                "1.3.6.1.2.1.1.3.0": "1234567",
                "1.3.6.1.4.1.9.9.43.1.1.6.0": "config changed",
                "1.3.6.1.4.1.9.9.43.1.1.7.0": "admin",
            },
        }

        alert = snmp_provider.format_alert(event)

        assert alert.snmpVarbinds is not None
        assert len(alert.snmpVarbinds) == 3
        assert "config changed" in str(alert.snmpVarbinds.values())

    def test_parse_severity_from_field(self, snmp_provider):
        """Test parsing severity from explicit field."""
        test_cases = [
            ({"severity": "critical"}, AlertSeverity.CRITICAL),
            ({"severity": "warning"}, AlertSeverity.WARNING),
            ({"priority": "error"}, AlertSeverity.HIGH),
            ({"level": "info"}, AlertSeverity.INFO),
            ({"alarmSeverity": "5"}, AlertSeverity.LOW),
        ]

        for event_update, expected_severity in test_cases:
            base_event = {
                "version": "v2c",
                "source": "192.168.1.1",
            }
            base_event.update(event_update)

            alert = snmp_provider.format_alert(base_event)
            assert alert.severity == expected_severity, f"Failed for {event_update}"

    def test_parse_status_from_field(self, snmp_provider):
        """Test parsing status from explicit field."""
        test_cases = [
            ({"status": "up"}, AlertStatus.RESOLVED),
            ({"status": "down"}, AlertStatus.FIRING),
            ({"state": "ok"}, AlertStatus.RESOLVED),
            ({"state": "failed"}, AlertStatus.FIRING),
        ]

        for event_update, expected_status in test_cases:
            base_event = {
                "version": "v2c",
                "source": "192.168.1.1",
            }
            base_event.update(event_update)

            alert = snmp_provider.format_alert(base_event)
            assert alert.status == expected_status, f"Failed for {event_update}"

    def test_parse_cisco_trap(self, snmp_provider):
        """Test parsing Cisco-specific trap."""
        event = {
            "version": "v2c",
            "community": "public",
            "snmpTrapOID": "1.3.6.1.4.1.9.9.43.2.0.1",
            "agent_addr": "10.1.1.1",
            "specificTrap": "ciscoConfigManEvent",
            "varbinds": {
                "ccmHistoryRunningLastChanged": "123456",
                "ccmHistoryRunningLastSaved": "123400",
                "ccmHistoryStartupLastChanged": "123000",
            },
        }

        alert = snmp_provider.format_alert(event)

        assert alert.snmpOid == "1.3.6.1.4.1.9.9.43.2.0.1"
        assert alert.snmpSource == "10.1.1.1"
        assert "ciscoConfigManEvent" in alert.id

    def test_parse_snmp_v3_trap(self, snmp_provider):
        """Test parsing SNMPv3 trap."""
        event = {
            "version": "v3",
            "snmpVersion": "v3",
            "source": "192.168.1.200",
            "oid": "1.3.6.1.6.3.1.1.5.1",
            "severity": "warning",
            "message": "Authentication failure detected",
        }

        alert = snmp_provider.format_alert(event)

        assert alert.snmpVersion == "v3"
        assert "Authentication failure" in alert.description

    def test_default_severity(self, snmp_provider):
        """Test default severity when not specified."""
        event = {
            "version": "v2c",
            "source": "192.168.1.1",
        }

        alert = snmp_provider.format_alert(event)

        assert alert.severity == AlertSeverity.INFO

    def test_default_status(self, snmp_provider):
        """Test default status for traps."""
        event = {
            "version": "v2c",
            "source": "192.168.1.1",
        }

        alert = snmp_provider.format_alert(event)

        # Traps default to FIRING
        assert alert.status == AlertStatus.FIRING

    def test_alert_id_uniqueness(self, snmp_provider):
        """Test that different traps generate different IDs."""
        event1 = {
            "version": "v2c",
            "source": "192.168.1.1",
            "enterprise": "1.3.6.1.4.1.1.1",
            "specificTrap": "1",
        }
        event2 = {
            "version": "v2c",
            "source": "192.168.1.2",
            "enterprise": "1.3.6.1.4.1.1.1",
            "specificTrap": "1",
        }

        alert1 = snmp_provider.format_alert(event1)
        alert2 = snmp_provider.format_alert(event2)

        assert alert1.id != alert2.id

    def test_description_formatting(self, snmp_provider):
        """Test alert description formatting."""
        event = {
            "version": "v2c",
            "source": "192.168.1.1",
            "trapType": "coldStart",
            "uptime": "12345",
            "message": "System rebooted",
        }

        alert = snmp_provider.format_alert(event)

        assert "coldStart" in alert.description
        assert "12345" in alert.description
        assert "System rebooted" in alert.description

    def test_oid_in_varbinds(self, snmp_provider):
        """Test extracting OID values from top-level event."""
        event = {
            "version": "v2c",
            "source": "192.168.1.1",
            "1.3.6.1.2.1.1.3.0": "123456",  # sysUpTimeInstance
            "1.3.6.1.4.1.9.2.1.1.1.0": "Buffer overflow",  # cisco specific
        }

        alert = snmp_provider.format_alert(event)

        assert "1.3.6.1.2.1.1.3.0" in alert.snmpVarbinds
        assert alert.snmpVarbinds["1.3.6.1.2.1.1.3.0"] == "123456"

    def test_parse_numeric_severity(self, snmp_provider):
        """Test parsing numeric severity values."""
        test_cases = [
            ({"severity": "0"}, AlertSeverity.CRITICAL),
            ({"severity": "1"}, AlertSeverity.CRITICAL),
            ({"severity": "2"}, AlertSeverity.HIGH),
            ({"severity": "3"}, AlertSeverity.WARNING),
            ({"severity": "4"}, AlertSeverity.INFO),
            ({"severity": "5"}, AlertSeverity.LOW),
        ]

        for event_update, expected_severity in test_cases:
            base_event = {
                "version": "v2c",
                "source": "192.168.1.1",
            }
            base_event.update(event_update)

            alert = snmp_provider.format_alert(base_event)
            assert alert.severity == expected_severity, f"Failed for severity {event_update}"


if __name__ == "__main__":
    pytest.main([__file__])
