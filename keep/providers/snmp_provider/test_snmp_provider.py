"""
Tests for SNMP Provider
"""

import pytest
from unittest.mock import Mock, patch

from keep.providers.snmp_provider.snmp_provider import SnmpProvider, SnmpProviderAuthConfig


class TestSnmpProvider:
    """Test cases for SNMP Provider"""

    def test_validate_config_v2c(self):
        """Test validation of SNMPv2c config"""
        config = {
            "host": "192.168.1.1",
            "port": 161,
            "version": "2c",
            "community": "public"
        }
        auth_config = SnmpProviderAuthConfig(**config)
        assert auth_config.host == "192.168.1.1"
        assert auth_config.version == "2c"
        assert auth_config.community == "public"

    def test_validate_config_v3(self):
        """Test validation of SNMPv3 config"""
        config = {
            "host": "192.168.1.1",
            "port": 161,
            "version": "3",
            "username": "admin",
            "auth_key": "authpass",
            "priv_key": "privpass"
        }
        auth_config = SnmpProviderAuthConfig(**config)
        assert auth_config.version == "3"
        assert auth_config.username == "admin"

    def test_invalid_version(self):
        """Test validation rejects invalid SNMP version"""
        config = {
            "host": "192.168.1.1",
            "version": "4"  # Invalid
        }
        with pytest.raises(ValueError):
            SnmpProviderAuthConfig(**config)

    @patch("keep.providers.snmp_provider.snmp_provider.getCmd")
    def test_get_oid_success(self, mock_getCmd):
        """Test successful OID retrieval"""
        # Mock successful SNMP response
        mock_getCmd.return_value = iter([
            (None, 0, 0, [(Mock(), Mock())])
        ])
        
        # TODO: Complete test implementation
        pass

    @patch("keep.providers.snmp_provider.snmp_provider.getCmd")
    def test_get_oid_failure(self, mock_getCmd):
        """Test OID retrieval failure"""
        # Mock SNMP error
        mock_getCmd.return_value = iter([
            ("Timeout", 0, 0, [])
        ])
        
        # TODO: Complete test implementation
        pass

    def test_format_alert(self):
        """Test alert formatting"""
        event = {
            "id": "test-alert",
            "name": "Test Alert",
            "severity": "CRITICAL",
            "status": "ACTIVE",
            "description": "Test description",
            "source": "snmp-device",
            "timestamp": "2026-02-02T12:00:00Z"
        }
        
        alert = SnmpProvider._format_alert(event, "test-provider", "snmp")
        
        assert alert.id == "test-alert"
        assert alert.name == "Test Alert"
        assert alert.severity.value == "critical"
        assert alert.status.value == "firing"
