"""
Tests for the SNMP Provider.
"""

import datetime
import hashlib
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus


class TestSnmpProviderFormatAlert:
    """Test the SNMP provider's _format_alert method."""

    def test_format_alert_link_down(self):
        """Test formatting a linkDown trap."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_ip": "192.168.1.1",
            "message": "Interface eth0 is down",
            "var_binds": {
                "ifIndex": "1",
                "ifDescr": "eth0",
                "ifOperStatus": "down",
            },
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "linkDown"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING
        assert "snmp" in alert.source
        assert alert.labels["source_ip"] == "192.168.1.1"
        assert alert.labels["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
        assert alert.labels["ifDescr"] == "eth0"

    def test_format_alert_link_up(self):
        """Test formatting a linkUp trap."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "source_ip": "192.168.1.1",
            "var_binds": {
                "ifIndex": "1",
                "ifDescr": "eth0",
                "ifOperStatus": "up",
            },
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "linkUp"
        assert alert.severity == AlertSeverity.INFO

    def test_format_alert_cold_start(self):
        """Test formatting a coldStart trap."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "source_ip": "192.168.1.2",
            "var_binds": {
                "sysUpTime": "0",
            },
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "coldStart"
        assert alert.severity == AlertSeverity.WARNING

    def test_format_alert_auth_failure(self):
        """Test formatting an authenticationFailure trap."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "source_ip": "192.168.1.100",
            "var_binds": {
                "snmpTrapCommunity": "wrong_community",
            },
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "authenticationFailure"
        assert alert.severity == AlertSeverity.WARNING

    def test_format_alert_critical_severity(self):
        """Test that 'critical' in event triggers CRITICAL severity."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.4.1.9999.1",
            "source_ip": "192.168.1.1",
            "message": "CRITICAL: System failure",
            "var_binds": {},
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_fingerprint(self):
        """Test that fingerprint is correctly generated."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_ip": "192.168.1.1",
            "var_binds": {},
        }

        alert = SnmpProvider._format_alert(event)

        expected_fingerprint = hashlib.sha256(
            "1.3.6.1.6.3.1.1.5.3:192.168.1.1".encode()
        ).hexdigest()[:16]

        assert alert.fingerprint == expected_fingerprint

    def test_format_alert_var_binds_as_list(self):
        """Test formatting when var_binds is a list."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        event = {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_ip": "192.168.1.1",
            "var_binds": ["value1", "value2", "value3"],
        }

        alert = SnmpProvider._format_alert(event)

        assert "value1" in alert.description
        assert "value2" in alert.description


class TestSnmpProviderConfig:
    """Test the SNMP provider configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProviderAuthConfig

        config = SnmpProviderAuthConfig()

        assert config.listen_port == 162
        assert config.listen_address == "0.0.0.0"
        assert config.community_string == "public"
        assert config.snmp_version == "2c"
        assert config.snmpv3_user is None

    def test_config_custom_values(self):
        """Test custom configuration values."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProviderAuthConfig

        config = SnmpProviderAuthConfig(
            listen_port=1162,
            listen_address="127.0.0.1",
            community_string="private",
            snmp_version="3",
            snmpv3_user="keepuser",
            snmpv3_auth_protocol="SHA256",
            snmpv3_auth_password="authpass",
            snmpv3_priv_protocol="AES256",
            snmpv3_priv_password="privpass",
        )

        assert config.listen_port == 1162
        assert config.listen_address == "127.0.0.1"
        assert config.community_string == "private"
        assert config.snmp_version == "3"
        assert config.snmpv3_user == "keepuser"
        assert config.snmpv3_auth_protocol == "SHA256"


class TestSnmpProviderTrapName:
    """Test the trap name extraction."""

    def test_get_trap_name_standard_traps(self):
        """Test standard trap name extraction."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        # Create a mock provider instance
        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.authentication = {
            "listen_port": 1162,
            "community_string": "public",
        }

        with patch.object(SnmpProvider, "validate_config"):
            provider = SnmpProvider(mock_context, "test", mock_config)

            assert provider._get_trap_name("1.3.6.1.6.3.1.1.5.1") == "coldStart"
            assert provider._get_trap_name("1.3.6.1.6.3.1.1.5.2") == "warmStart"
            assert provider._get_trap_name("1.3.6.1.6.3.1.1.5.3") == "linkDown"
            assert provider._get_trap_name("1.3.6.1.6.3.1.1.5.4") == "linkUp"
            assert provider._get_trap_name("1.3.6.1.6.3.1.1.5.5") == "authenticationFailure"
            assert provider._get_trap_name("1.3.6.1.6.3.1.1.5.6") == "egpNeighborLoss"

    def test_get_trap_name_unknown_trap(self):
        """Test unknown trap name extraction."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.authentication = {
            "listen_port": 1162,
            "community_string": "public",
        }

        with patch.object(SnmpProvider, "validate_config"):
            provider = SnmpProvider(mock_context, "test", mock_config)

            assert provider._get_trap_name("1.3.6.1.4.1.9999.1.2.3") == "snmp-trap-1.3.6.1.4.1.9999.1.2.3"
            assert provider._get_trap_name(None) == "snmp-trap-unknown"


class TestSnmpProviderSeverity:
    """Test severity determination."""

    def test_get_severity_standard_traps(self):
        """Test severity for standard traps."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.authentication = {
            "listen_port": 1162,
            "community_string": "public",
        }

        with patch.object(SnmpProvider, "validate_config"):
            provider = SnmpProvider(mock_context, "test", mock_config)

            assert provider._get_severity("1.3.6.1.6.3.1.1.5.3", {}) == AlertSeverity.HIGH  # linkDown
            assert provider._get_severity("1.3.6.1.6.3.1.1.5.4", {}) == AlertSeverity.INFO  # linkUp
            assert provider._get_severity("1.3.6.1.6.3.1.1.5.1", {}) == AlertSeverity.WARNING  # coldStart

    def test_get_severity_from_trap_data(self):
        """Test severity extraction from trap data."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.authentication = {
            "listen_port": 1162,
            "community_string": "public",
        }

        with patch.object(SnmpProvider, "validate_config"):
            provider = SnmpProvider(mock_context, "test", mock_config)

            # Test critical severity from data
            assert provider._get_severity(
                "1.3.6.1.4.1.9999.1",
                {"status": "CRITICAL: System failure"}
            ) == AlertSeverity.CRITICAL

            # Test error/high severity from data
            assert provider._get_severity(
                "1.3.6.1.4.1.9999.1",
                {"status": "ERROR: Disk failure"}
            ) == AlertSeverity.HIGH


class TestSnmpProviderSimulateAlert:
    """Test alert simulation."""

    def test_simulate_alert(self):
        """Test that simulate_alert returns a valid trap."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        alert = SnmpProvider.simulate_alert()

        assert "trap_oid" in alert
        assert "source_ip" in alert
        assert "var_binds" in alert or "message" in alert


class TestSnmpProviderStatus:
    """Test provider status."""

    def test_status_stopped(self):
        """Test status when stopped."""
        from keep.providers.snmp_provider.snmp_provider import SnmpProvider

        mock_context = MagicMock()
        mock_config = MagicMock()
        mock_config.authentication = {
            "listen_port": 1162,
            "listen_address": "0.0.0.0",
            "community_string": "public",
            "snmp_version": "2c",
        }

        with patch.object(SnmpProvider, "validate_config"):
            provider = SnmpProvider(mock_context, "test", mock_config)
            provider.authentication_config = MagicMock()
            provider.authentication_config.listen_port = 1162
            provider.authentication_config.listen_address = "0.0.0.0"

            status = provider.status()

            assert status["status"] == "stopped"
            assert status["port"] == 1162
            assert status["address"] == "0.0.0.0"
