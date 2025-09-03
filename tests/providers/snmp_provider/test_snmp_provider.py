"""
Unit tests for SNMP Provider.
"""

import datetime
import pytest
from unittest.mock import Mock, patch, MagicMock
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider, SnmpProviderAuthConfig
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus


class TestSnmpProviderAuthConfig:
    """Test SNMP provider authentication configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SnmpProviderAuthConfig()
        assert config.listen_address == "0.0.0.0"
        assert config.listen_port == 162
        assert config.community_string == "public"
        assert config.security_name is None
        assert config.auth_protocol is None
        assert config.auth_key is None
        assert config.priv_protocol is None
        assert config.priv_key is None
        
    def test_custom_config(self):
        """Test custom configuration values."""
        config = SnmpProviderAuthConfig(
            listen_address="192.168.1.100",
            listen_port=1162,
            community_string="private",
            security_name="testuser",
            auth_protocol="SHA",
            auth_key="testauth123",
            priv_protocol="AES",
            priv_key="testpriv123"
        )
        assert config.listen_address == "192.168.1.100"
        assert config.listen_port == 1162
        assert config.community_string == "private"
        assert config.security_name == "testuser"
        assert config.auth_protocol == "SHA"
        assert config.auth_key == "testauth123"
        assert config.priv_protocol == "AES"
        assert config.priv_key == "testpriv123"


class TestSnmpProvider:
    """Test SNMP provider functionality."""
    
    @pytest.fixture
    def mock_context_manager(self):
        """Create a mock context manager."""
        context_manager = Mock(spec=ContextManager)
        context_manager.tenant_id = "test-tenant"
        return context_manager
        
    @pytest.fixture
    def basic_config(self):
        """Create basic provider configuration."""
        return ProviderConfig(
            authentication={
                "listen_address": "127.0.0.1",
                "listen_port": 1162,
                "community_string": "public"
            }
        )
        
    @pytest.fixture
    def snmpv3_config(self):
        """Create SNMPv3 provider configuration."""
        return ProviderConfig(
            authentication={
                "listen_address": "127.0.0.1", 
                "listen_port": 1162,
                "community_string": "public",
                "security_name": "testuser",
                "auth_protocol": "SHA",
                "auth_key": "testauth123",
                "priv_protocol": "AES",
                "priv_key": "testpriv123"
            }
        )
        
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_provider_initialization(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test provider initialization."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)
        
        assert provider.provider_id == "test-snmp"
        assert provider.context_manager == mock_context_manager
        assert provider.config == basic_config
        assert provider.snmp_engine is None
        assert provider.trap_receiver_task is None
        mock_start_receiver.assert_called_once()
        
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_config_basic(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test basic configuration validation."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)
        provider.validate_config()
        
        assert isinstance(provider.authentication_config, SnmpProviderAuthConfig)
        assert provider.authentication_config.listen_address == "127.0.0.1"
        assert provider.authentication_config.listen_port == 1162
        assert provider.authentication_config.community_string == "public"
        
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_config_snmpv3(self, mock_start_receiver, mock_context_manager, snmpv3_config):
        """Test SNMPv3 configuration validation."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", snmpv3_config)
        provider.validate_config()
        
        assert provider.authentication_config.security_name == "testuser"
        assert provider.authentication_config.auth_protocol == "SHA"
        assert provider.authentication_config.auth_key == "testauth123"
        assert provider.authentication_config.priv_protocol == "AES"
        assert provider.authentication_config.priv_key == "testpriv123"
        
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_config_invalid_port(self, mock_start_receiver, mock_context_manager):
        """Test configuration validation with invalid port."""
        config = ProviderConfig(
            authentication={
                "listen_address": "127.0.0.1",
                "listen_port": 70000,  # Invalid port
                "community_string": "public"
            }
        )
        
        provider = SnmpProvider(mock_context_manager, "test-snmp", config)
        
        with pytest.raises(ValueError, match="listen_port must be between 1 and 65535"):
            provider.validate_config()
            
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_config_snmpv3_missing_auth_key(self, mock_start_receiver, mock_context_manager):
        """Test SNMPv3 configuration validation with missing auth key."""
        config = ProviderConfig(
            authentication={
                "listen_address": "127.0.0.1",
                "listen_port": 1162,
                "security_name": "testuser",
                "auth_protocol": "SHA",
                # Missing auth_key
            }
        )
        
        provider = SnmpProvider(mock_context_manager, "test-snmp", config)
        
        with pytest.raises(ValueError, match="auth_key is required when auth_protocol is specified"):
            provider.validate_config()
            
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_config_snmpv3_missing_priv_key(self, mock_start_receiver, mock_context_manager):
        """Test SNMPv3 configuration validation with missing priv key."""
        config = ProviderConfig(
            authentication={
                "listen_address": "127.0.0.1",
                "listen_port": 1162,
                "security_name": "testuser",
                "auth_protocol": "SHA",
                "auth_key": "testauth123",
                "priv_protocol": "AES",
                # Missing priv_key
            }
        )
        
        provider = SnmpProvider(mock_context_manager, "test-snmp", config)
        
        with pytest.raises(ValueError, match="priv_key is required when priv_protocol is specified"):
            provider.validate_config()
            
    @patch('keep.providers.snmp_provider.snmp_provider.engine.SnmpEngine')
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_scopes_success(self, mock_start_receiver, mock_snmp_engine, mock_context_manager, basic_config):
        """Test successful scope validation."""
        mock_engine_instance = Mock()
        mock_snmp_engine.return_value = mock_engine_instance
        
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)
        scopes = provider.validate_scopes()
        
        assert scopes["receive_traps"] is True
        mock_engine_instance.closeDispatcher.assert_called_once()
        
    @patch('keep.providers.snmp_provider.snmp_provider.engine.SnmpEngine')
    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_validate_scopes_failure(self, mock_start_receiver, mock_snmp_engine, mock_context_manager, basic_config):
        """Test scope validation failure."""
        mock_snmp_engine.side_effect = Exception("SNMP engine error")
        
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)
        scopes = provider.validate_scopes()
        
        assert "receive_traps" in scopes
        assert "Failed to initialize SNMP engine" in scopes["receive_traps"]

    def test_format_alert_basic(self):
        """Test basic alert formatting."""
        event = {
            "name": "coldStart",
            "description": "System cold start",
            "severity": "info",
            "status": "firing",
            "source": "192.168.1.1",
            "fingerprint": "snmp-coldstart-192.168.1.1",
            "lastReceived": "2024-01-01T12:00:00Z",
            "labels": {
                "trap_oid": "1.3.6.1.6.3.1.1.5.1",
                "provider": "snmp"
            }
        }

        alert = SnmpProvider._format_alert(event)

        assert isinstance(alert, AlertDto)
        assert alert.name == "coldStart"
        assert alert.description == "System cold start"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING
        assert alert.source == "192.168.1.1"
        assert alert.fingerprint == "snmp-coldstart-192.168.1.1"
        assert alert.labels["trap_oid"] == "1.3.6.1.6.3.1.1.5.1"

    def test_format_alert_with_enum_values(self):
        """Test alert formatting with enum values."""
        event = {
            "name": "linkDown",
            "description": "Interface down",
            "severity": AlertSeverity.WARNING,
            "status": AlertStatus.FIRING,
            "source": "192.168.1.2",
            "fingerprint": "snmp-linkdown-192.168.1.2",
            "labels": {}
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_format_alert_minimal(self):
        """Test alert formatting with minimal data."""
        event = {}

        alert = SnmpProvider._format_alert(event)

        assert alert.name == "SNMP Trap"
        assert alert.description == "SNMP trap received"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING
        assert alert.source == "unknown"
        assert isinstance(alert.lastReceived, datetime.datetime)

    def test_format_alert_invalid_severity(self):
        """Test alert formatting with invalid severity."""
        event = {
            "severity": "invalid_severity",
            "status": "invalid_status"
        }

        alert = SnmpProvider._format_alert(event)

        assert alert.severity == AlertSeverity.INFO  # Default fallback
        assert alert.status == AlertStatus.FIRING    # Default fallback

    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_create_alert_from_trap(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test creating alert from trap data."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)

        trap_data = {
            "timestamp": "2024-01-01T12:00:00Z",
            "source": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "variables": {
                "1.3.6.1.2.1.1.3.0": "12345",  # sysUpTime
                "1.3.6.1.2.1.1.5.0": "test-device"  # sysName
            }
        }

        alert_data = provider._create_alert_from_trap(trap_data)

        assert alert_data["name"] == "coldStart"
        assert alert_data["severity"] == AlertSeverity.INFO.value
        assert alert_data["source"] == "192.168.1.1"
        assert alert_data["fingerprint"] == "snmp-1.3.6.1.6.3.1.1.5.1-192.168.1.1"
        assert "Source: 192.168.1.1" in alert_data["description"]
        assert alert_data["labels"]["trap_oid"] == "1.3.6.1.6.3.1.1.5.1"

    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_create_alert_from_trap_unknown_oid(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test creating alert from trap with unknown OID."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)

        trap_data = {
            "timestamp": "2024-01-01T12:00:00Z",
            "source": "192.168.1.1",
            "trap_oid": "1.2.3.4.5.6.7.8.9",  # Unknown OID
            "variables": {}
        }

        alert_data = provider._create_alert_from_trap(trap_data)

        assert alert_data["name"] == "SNMP Trap 1.2.3.4.5.6.7.8.9"
        assert alert_data["severity"] == AlertSeverity.INFO.value  # Default severity

    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_extract_trap_data(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test extracting trap data from variable bindings."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)

        # Mock variable bindings
        mock_var_binds = [
            (Mock(spec=str), Mock()),  # Mock OID and value
            (Mock(spec=str), Mock()),
        ]

        # Configure mocks
        mock_var_binds[0][0].__str__ = Mock(return_value="1.3.6.1.6.3.1.1.4.1.0")
        mock_var_binds[0][1].__str__ = Mock(return_value="1.3.6.1.6.3.1.1.5.1")
        mock_var_binds[1][0].__str__ = Mock(return_value="1.3.6.1.2.1.1.3.0")
        mock_var_binds[1][1].prettyPrint = Mock(return_value="12345")

        # Mock callback context
        mock_cb_ctx = Mock()
        mock_cb_ctx.transportAddress = ("192.168.1.1", 12345)

        trap_data = provider._extract_trap_data(mock_var_binds, mock_cb_ctx)

        assert trap_data["source"] == "192.168.1.1"
        assert trap_data["trap_oid"] == "1.3.6.1.6.3.1.1.5.1"
        assert "1.3.6.1.2.1.1.3.0" in trap_data["variables"]
        assert trap_data["variables"]["1.3.6.1.2.1.1.3.0"] == "12345"

    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_notify_not_implemented(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test that notify method raises NotImplementedError."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)

        with pytest.raises(NotImplementedError, match="SNMP provider is designed for receiving traps"):
            provider._notify()

    @patch('keep.providers.snmp_provider.snmp_provider.SnmpProvider.start_trap_receiver')
    def test_query_not_implemented(self, mock_start_receiver, mock_context_manager, basic_config):
        """Test that query method raises NotImplementedError."""
        provider = SnmpProvider(mock_context_manager, "test-snmp", basic_config)

        with pytest.raises(NotImplementedError, match="SNMP provider is designed for receiving traps"):
            provider._query()
