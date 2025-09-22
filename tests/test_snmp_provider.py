"""
Unit tests for SNMP Provider
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.snmp_provider.snmp_provider import SnmpProvider, SnmpProviderAuthConfig
from keep.providers.models.provider_config import ProviderConfig
from keep.api.models.alert import AlertSeverity


class TestSnmpProvider:
    """Test cases for SNMP Provider."""

    @pytest.fixture
    def context_manager(self):
        """Create a mock context manager."""
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def snmp_config(self):
        """Create a test SNMP configuration."""
        return ProviderConfig(
            description="Test SNMP Provider",
            authentication={
                "listen_address": "0.0.0.0",
                "port": 1162,
                "community": "public",
                "severity_mapping": json.dumps({
                    "1.3.6.1.6.3.1.1.5.1": "INFO",
                    "1.3.6.1.6.3.1.1.5.2": "WARNING", 
                    "1.3.6.1.6.3.1.1.5.3": "ERROR",
                    "1.3.6.1.6.3.1.1.5.4": "CRITICAL"
                })
            },
        )

    @pytest.fixture
    def snmp_provider(self, context_manager, snmp_config):
        """Create an SNMP provider instance."""
        return SnmpProvider(
            context_manager=context_manager,
            provider_id="test_snmp_provider",
            config=snmp_config,
        )

    def test_snmp_provider_initialization(self, snmp_provider):
        """Test SNMP provider initialization."""
        assert snmp_provider.provider_id == "test_snmp_provider"
        assert snmp_provider.authentication_config.listen_address == "0.0.0.0"
        assert snmp_provider.authentication_config.port == 1162
        assert snmp_provider.authentication_config.community == "public"
        assert not snmp_provider.running
        assert snmp_provider._severity_mapping is not None

    def test_severity_mapping_parsing(self, snmp_provider):
        """Test that severity mapping is correctly parsed."""
        expected_mapping = {
            "1.3.6.1.6.3.1.1.5.1": "INFO",
            "1.3.6.1.6.3.1.1.5.2": "WARNING",
            "1.3.6.1.6.3.1.1.5.3": "ERROR",
            "1.3.6.1.6.3.1.1.5.4": "CRITICAL"
        }
        assert snmp_provider._severity_mapping == expected_mapping

    def test_parse_severity(self, snmp_provider):
        """Test severity parsing from string to AlertSeverity enum."""
        assert snmp_provider._parse_severity("INFO") == AlertSeverity.INFO
        assert snmp_provider._parse_severity("WARNING") == AlertSeverity.WARNING
        assert snmp_provider._parse_severity("ERROR") == AlertSeverity.HIGH
        assert snmp_provider._parse_severity("CRITICAL") == AlertSeverity.CRITICAL
        assert snmp_provider._parse_severity("UNKNOWN") == AlertSeverity.WARNING

    def test_determine_severity_with_mapping(self, snmp_provider):
        """Test severity determination based on OID mapping."""
        oids = ["1.3.6.1.6.3.1.1.5.1", "1.3.6.1.2.1.1.1.0"]
        data = {"1.3.6.1.6.3.1.1.5.1": "coldStart", "1.3.6.1.2.1.1.1.0": "Test Device"}
        
        severity = snmp_provider._determine_severity(oids, data)
        assert severity == AlertSeverity.INFO

    def test_determine_severity_default(self, snmp_provider):
        """Test default severity when no mapping matches."""
        oids = ["1.3.6.1.2.1.1.1.0"]
        data = {"1.3.6.1.2.1.1.1.0": "Test Device"}
        
        severity = snmp_provider._determine_severity(oids, data)
        assert severity == AlertSeverity.WARNING

    @patch('keep.providers.snmp_provider.snmp_provider.socket.socket')
    def test_validate_scopes_success(self, mock_socket, snmp_provider):
        """Test successful scope validation."""
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        
        result = snmp_provider.validate_scopes()
        assert result == {"receive_traps": True}
        mock_socket_instance.bind.assert_called_once_with(("0.0.0.0", 1162))
        mock_socket_instance.close.assert_called_once()

    @patch('keep.providers.snmp_provider.snmp_provider.socket.socket')
    def test_validate_scopes_failure(self, mock_socket, snmp_provider):
        """Test scope validation failure when port is unavailable."""
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket_instance.bind.side_effect = OSError("Address already in use")
        
        result = snmp_provider.validate_scopes()
        assert "receive_traps" in result
        assert "Failed to bind" in result["receive_traps"]

    @patch('keep.providers.snmp_provider.snmp_provider.engine.SnmpEngine')
    @patch('keep.providers.snmp_provider.snmp_provider.config')
    @patch('keep.providers.snmp_provider.snmp_provider.ntfrcv.NotificationReceiver')
    @patch('keep.providers.snmp_provider.snmp_provider.asyncio.new_event_loop')
    def test_handle_trap_processing(self, mock_loop, mock_ntfrcv, mock_config, mock_engine, snmp_provider):
        """Test SNMP trap processing and alert creation."""
        # Mock the trap data
        mock_oid1 = Mock()
        mock_oid1.__str__ = lambda self: "1.3.6.1.6.3.1.1.5.1"
        
        mock_oid2 = Mock()
        mock_oid2.__str__ = lambda self: "1.3.6.1.2.1.1.1.0"
        
        mock_val1 = Mock()
        mock_val1.__class__.__name__ = "OctetString"
        mock_val1.__str__ = lambda self: "coldStart"
        
        mock_val2 = Mock()
        mock_val2.__class__.__name__ = "OctetString"
        mock_val2.__str__ = lambda self: "Test Device"
        
        var_binds = [(mock_oid1, mock_val1), (mock_oid2, mock_val2)]
        
        # Mock _push_alert to capture the alert
        with patch.object(snmp_provider, '_push_alert') as mock_push_alert:
            snmp_provider._handle_trap(
                snmp_engine=Mock(),
                state_reference=Mock(),
                context_engine_id=Mock(),
                context_name=Mock(),
                var_binds=var_binds,
                cb_ctx=Mock()
            )
            
            # Verify that _push_alert was called
            mock_push_alert.assert_called_once()
            
            # Get the alert that was pushed
            alert = mock_push_alert.call_args[0][0]
            
            # Verify alert structure
            assert alert["title"] == "SNMP Trap Received"
            assert "SNMP Trap received with the following data:" in alert["description"]
            assert alert["severity"] == AlertSeverity.INFO.value
            assert alert["source"] == ["snmp"]
            assert "1.3.6.1.6.3.1.1.5.1" in alert["fingerprint"]
            assert "1.3.6.1.2.1.1.1.0" in alert["fingerprint"]
            
            # Verify raw data
            raw_data = json.loads(alert["raw_data"])
            assert raw_data["1.3.6.1.6.3.1.1.5.1"] == "coldStart"
            assert raw_data["1.3.6.1.2.1.1.1.0"] == "Test Device"

    def test_handle_trap_with_critical_severity(self, snmp_provider):
        """Test trap processing with critical severity mapping."""
        # Mock trap data for critical alert
        mock_oid1 = Mock()
        mock_oid1.__str__ = lambda self: "1.3.6.1.6.3.1.1.5.4"  # Maps to CRITICAL
        
        mock_val1 = Mock()
        mock_val1.__class__.__name__ = "OctetString"
        mock_val1.__str__ = lambda self: "authenticationFailure"
        
        var_binds = [(mock_oid1, mock_val1)]
        
        with patch.object(snmp_provider, '_push_alert') as mock_push_alert:
            snmp_provider._handle_trap(
                snmp_engine=Mock(),
                state_reference=Mock(),
                context_engine_id=Mock(),
                context_name=Mock(),
                var_binds=var_binds,
                cb_ctx=Mock()
            )
            
            alert = mock_push_alert.call_args[0][0]
            assert alert["severity"] == AlertSeverity.CRITICAL.value

    def test_handle_trap_error_handling(self, snmp_provider):
        """Test error handling in trap processing."""
        # Create a var_binds that will cause an error
        mock_oid = Mock()
        mock_oid.__str__ = Mock(side_effect=Exception("OID parsing error"))
        
        mock_val = Mock()
        var_binds = [(mock_oid, mock_val)]
        
        # Should not raise exception, should log error instead
        with patch.object(snmp_provider.logger, 'error') as mock_logger:
            snmp_provider._handle_trap(
                snmp_engine=Mock(),
                state_reference=Mock(),
                context_engine_id=Mock(),
                context_name=Mock(),
                var_binds=var_binds,
                cb_ctx=Mock()
            )
            
            # Verify error was logged
            mock_logger.assert_called()

    def test_get_logs(self, snmp_provider):
        """Test log retrieval functionality."""
        logs = snmp_provider.get_logs(limit=10)
        
        assert isinstance(logs, list)
        assert len(logs) >= 2  # Should have debug info and status logs
        
        # Check for expected log entries
        log_messages = [log["message"] for log in logs]
        assert any("SNMP Provider Debug Information" in msg for msg in log_messages)
        assert any("SNMP trap receiver status" in msg for msg in log_messages)

    def test_debug_info(self, snmp_provider):
        """Test debug information generation."""
        debug_info = snmp_provider.debug_info()
        
        assert "provider_id" in debug_info
        assert "running" in debug_info
        assert "configuration" in debug_info
        assert "port_test" in debug_info
        assert "snmp_engine" in debug_info
        
        assert debug_info["provider_id"] == "test_snmp_provider"
        assert debug_info["configuration"]["listen_address"] == "0.0.0.0"
        assert debug_info["configuration"]["port"] == 1162

    def test_invalid_severity_mapping(self, context_manager):
        """Test handling of invalid severity mapping JSON."""
        config = ProviderConfig(
            description="Test SNMP Provider",
            authentication={
                "listen_address": "0.0.0.0",
                "port": 1162,
                "community": "public",
                "severity_mapping": "invalid json"
            },
        )
        
        # Create provider with invalid JSON - it should handle the error gracefully
        provider = SnmpProvider(
            context_manager=context_manager,
            provider_id="test_snmp_provider",
            config=config,
        )
        
        # Should have empty severity mapping due to JSON error
        assert provider._severity_mapping == {}

    def test_query_method(self, snmp_provider):
        """Test that query method returns None and logs warning."""
        with patch.object(snmp_provider.logger, 'warning') as mock_logger:
            result = snmp_provider._query()
            assert result is None
            mock_logger.assert_called_with("SNMP provider does not support querying")

    def test_notify_method(self, snmp_provider):
        """Test that notify method returns None and logs warning."""
        with patch.object(snmp_provider.logger, 'warning') as mock_logger:
            result = snmp_provider._notify()
            assert result is None
            mock_logger.assert_called_with("SNMP provider is a receiver and does not support direct notification")

    def test_is_consumer_property(self, snmp_provider):
        """Test that provider is marked as a consumer."""
        assert snmp_provider.is_consumer is True

    def test_status_method(self, snmp_provider):
        """Test status method returns running state."""
        assert snmp_provider.status() is False
        
        snmp_provider.running = True
        assert snmp_provider.status() is True

    def test_get_alert_schema(self):
        """Test alert schema structure."""
        schema = SnmpProvider.get_alert_schema()
        
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "title" in schema["properties"]
        assert "description" in schema["properties"]
        assert "severity" in schema["properties"]
        assert "source" in schema["properties"]
        assert "raw_data" in schema["properties"]
        
        # Check severity enum values
        severity_enum = schema["properties"]["severity"]["enum"]
        assert "info" in severity_enum
        assert "warning" in severity_enum
        assert "error" in severity_enum
        assert "critical" in severity_enum

    @patch('keep.providers.snmp_provider.snmp_provider.socket.socket')
    def test_dispose_cleanup(self, mock_socket, snmp_provider):
        """Test proper cleanup when disposing provider."""
        # Set up mock SNMP engine
        mock_engine = Mock()
        mock_transport_dispatcher = Mock()
        mock_engine.transportDispatcher = mock_transport_dispatcher
        snmp_provider.snmp_engine = mock_engine
        snmp_provider.running = True
        
        # Set up mock thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        snmp_provider.trap_thread = mock_thread
        
        # Call dispose
        snmp_provider.dispose()
        
        # Verify cleanup
        assert snmp_provider.running is False
        assert snmp_provider.snmp_engine is None
        mock_transport_dispatcher.jobFinished.assert_called_once_with(1)
        mock_transport_dispatcher.closeDispatcher.assert_called_once()
        mock_thread.join.assert_called_once_with(timeout=5.0)

    def test_dispose_when_not_running(self, snmp_provider):
        """Test dispose when provider is not running."""
        snmp_provider.running = False
        
        # Should return early without doing anything
        snmp_provider.dispose()
        
        # Verify state unchanged
        assert snmp_provider.running is False
        assert snmp_provider.snmp_engine is None
