import unittest
import asyncio
from unittest.mock import patch, MagicMock

from keep.providers.snmp_provider.snmp_provider import (
    SnmpProvider,
    SnmpProviderAuthConfig,
    SnmpVersion,
    SnmpAuthProtocol,
    SnmpPrivProtocol,
    SnmpSecurityLevel,
)
from keep.providers.models.provider_config import ProviderConfig
from keep.contextmanager.contextmanager import ContextManager
from keep.api.models.alert import AlertSeverity, AlertStatus


class TestSnmpProvider(unittest.TestCase):
    def setUp(self):
        self.context_manager = ContextManager(
            tenant_id="test_tenant",
            workflow_id="test_workflow",
        )

    def test_validate_config_v1(self):
        """Test validation of SNMPv1 configuration"""
        config = ProviderConfig(
            description="SNMP Provider",
            authentication={
                "host": "localhost",
                "port": 161,
                "version": SnmpVersion.V1,
                "community_string": "public",
            },
        )
        provider = SnmpProvider(
            context_manager=self.context_manager,
            provider_id="test_snmp",
            config=config,
        )
        # Should not raise any exceptions
        provider.validate_config()

    def test_validate_config_v2c(self):
        """Test validation of SNMPv2c configuration"""
        config = ProviderConfig(
            description="SNMP Provider",
            authentication={
                "host": "localhost",
                "port": 161,
                "version": SnmpVersion.V2C,
                "community_string": "public",
            },
        )
        provider = SnmpProvider(
            context_manager=self.context_manager,
            provider_id="test_snmp",
            config=config,
        )
        # Should not raise any exceptions
        provider.validate_config()

    def test_validate_config_v3_auth_no_priv(self):
        """Test validation of SNMPv3 configuration with auth but no privacy"""
        config = ProviderConfig(
            description="SNMP Provider",
            authentication={
                "host": "localhost",
                "port": 161,
                "version": SnmpVersion.V3,
                "username": "snmpuser",
                "auth_protocol": SnmpAuthProtocol.SHA,
                "auth_key": "authpass123",
                "security_level": SnmpSecurityLevel.AUTH_NO_PRIV,
            },
        )
        provider = SnmpProvider(
            context_manager=self.context_manager,
            provider_id="test_snmp",
            config=config,
        )
        # Should not raise any exceptions
        provider.validate_config()

    def test_validate_config_v3_auth_priv(self):
        """Test validation of SNMPv3 configuration with auth and privacy"""
        config = ProviderConfig(
            description="SNMP Provider",
            authentication={
                "host": "localhost",
                "port": 161,
                "version": SnmpVersion.V3,
                "username": "snmpuser",
                "auth_protocol": SnmpAuthProtocol.SHA,
                "auth_key": "authpass123",
                "priv_protocol": SnmpPrivProtocol.AES,
                "priv_key": "privpass123",
                "security_level": SnmpSecurityLevel.AUTH_PRIV,
            },
        )
        provider = SnmpProvider(
            context_manager=self.context_manager,
            provider_id="test_snmp",
            config=config,
        )
        # Should not raise any exceptions
        provider.validate_config()

    def test_validate_config_v1_missing_community(self):
        """Test validation fails when community string is missing for v1/v2c"""
        config = ProviderConfig(
            description="SNMP Provider",
            authentication={
                "host": "localhost",
                "port": 161,
                "version": SnmpVersion.V1,
            },
        )
        with self.assertRaisesRegex(ValueError, "Community string is required for SNMP v1/v2c"):
            provider = SnmpProvider(
                context_manager=self.context_manager,
                provider_id="test_snmp",
                config=config,
            )

    def test_validate_config_v3_missing_username(self):
        """Test validation fails when username is missing for v3"""
        config = ProviderConfig(
            description="SNMP Provider",
            authentication={
                "host": "localhost",
                "port": 161,
                "version": SnmpVersion.V3,
                "security_level": SnmpSecurityLevel.AUTH_NO_PRIV,
            },
        )
        with self.assertRaisesRegex(ValueError, "Username is required for SNMP v3"):
            provider = SnmpProvider(
                context_manager=self.context_manager,
                provider_id="test_snmp",
                config=config,
            )

    def test_format_alert(self):
        """Test alert formatting from SNMP trap data"""
        trap_data = {
            "enterprise_oid": "1.3.6.1.4.1.12345",
            "agent_addr": "192.168.1.1",
            "trap_type": "6",
            "var_binds": [
                {"oid": "1.3.6.1.2.1.1.3.0", "value": "System Uptime"},
                {"oid": "1.3.6.1.6.3.1.1.4.1.0", "value": "Link Down"},
                {"oid": "1.3.6.1.2.1.2.2.1.1.123", "value": "Interface 123"},
                {"oid": "1.3.6.1.2.1.2.2.1.7.123", "value": "Down"},
                {"oid": "1.3.6.1.2.1.2.2.1.8.123", "value": "Down"},
            ],
        }

        alert = SnmpProvider._format_alert(trap_data)
        
        self.assertIsNotNone(alert.id)
        self.assertTrue(alert.name.startswith("SNMP Trap from 192.168.1.1"))
        self.assertEqual(alert.severity, AlertSeverity.INFO.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        self.assertEqual(alert.source, ["192.168.1.1"])
        self.assertIsNotNone(alert.lastReceived)
        self.assertIsNotNone(alert.fingerprint)

    def test_format_alert_with_severity(self):
        """Test alert formatting with severity detection"""
        trap_data = {
            "enterprise_oid": "1.3.6.1.4.1.12345",
            "agent_addr": "192.168.1.1",
            "trap_type": "6",
            "var_binds": [
                {"oid": "1.3.6.1.2.1.1.3.0", "value": "System Uptime"},
                {"oid": "severity.1.2.3", "value": "critical"},
                {"oid": "1.3.6.1.2.1.2.2.1.1.123", "value": "Interface 123"},
            ],
        }

        alert = SnmpProvider._format_alert(trap_data)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)
        self.assertEqual(alert.source, ["192.168.1.1"])


if __name__ == "__main__":
    unittest.main() 