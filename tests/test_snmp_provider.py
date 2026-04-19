import pytest
from unittest.mock import MagicMock, patch
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.api.models.alert import AlertSeverity, AlertStatus

class TestSnmpProvider:
    @pytest.fixture
    def context_manager(self):
        return ContextManager(tenant_id="test-tenant")

    @pytest.fixture
    def snmp_config(self):
        return ProviderConfig(
            authentication={
                "port": 1162,
                "community": "public",
                "v3_user": "test-user",
                "v3_auth_key": "auth-key",
                "v3_priv_key": "priv-key"
            }
        )

    @pytest.fixture
    def snmp_provider(self, context_manager, snmp_config):
        return SnmpProvider(context_manager, "test-snmp", snmp_config)

    def test_validate_config(self, snmp_provider):
        snmp_provider.validate_config()
        assert snmp_provider.authentication_config.port == 1162
        assert snmp_provider.authentication_config.community == "public"
        assert snmp_provider.authentication_config.v3_user == "test-user"

    @patch("keep.providers.snmp_provider.snmp_provider.SnmpProvider._push_alert")
    def test_trap_callback(self, mock_push_alert, snmp_provider):
        # Prepare mock varbinds
        # 1.3.6.1.6.3.1.1.4.1.0 is the OID for snmpTrapOID.0
        var_binds = [
            ("1.3.6.1.2.1.1.3.0", "12345"),  # sysUpTime
            ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.4.1.2021.251.1"),  # trap OID
            ("1.3.6.1.4.1.2021.251.1.1", "Sample alert message") # custom varbind
        ]
        
        # Simulate callback
        snmp_provider._trap_callback(
            snmpEngine=None,
            stateReference=None,
            contextEngineId=None,
            contextName=None,
            varBinds=var_binds,
            cbCtx=None
        )
        
        # Verify push_alert was called
        mock_push_alert.assert_called_once()
        args, _ = mock_push_alert.call_args
        alert_data = args[0]
        
        assert alert_data["source"] == ["snmp"]
        assert "SNMP Trap: 1.3.6.1.4.1.2021.251.1" in alert_data["name"]
        assert "1.3.6.1.4.1.2021.251.1.1: Sample alert message" in alert_data["description"]
        assert alert_data["severity"] == AlertSeverity.INFO
        assert alert_data["status"] == AlertStatus.FIRING

    @patch("pysnmp.entity.config.addV1System")
    @patch("pysnmp.entity.config.addV3User")
    @patch("pysnmp.entity.config.addTransport")
    @patch("pysnmp.entity.rfc3413.ntfrcv.NotificationReceiver")
    @patch("pysnmp.carrier.asyncio.dgram.udp.UdpAsyncioTransport")
    def test_start_consume_logic(self, mock_udp, mock_ntfrcv, mock_transport, mock_v3, mock_v1, snmp_provider):
        snmp_provider.validate_config()
        
        # Mock asyncio loop and related functions
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # We want to test the setup logic without actually running the infinite loop
            # setting consume = False here will make start_consume's loop exit immediately 
            # if we don't overwrite it inside the method, but start_consume does overwrite it.
            # So we mock run_until_complete to ensure we don't hang.
            mock_loop.run_until_complete = MagicMock()
            
            snmp_provider.start_consume()
            
            # Verify setup calls
            mock_v1.assert_called_with(snmp_provider.snmp_engine, "keep-area", "public")
            mock_v3.assert_called()
            mock_transport.assert_called()
            mock_ntfrcv.assert_called_with(snmp_provider.snmp_engine, snmp_provider._trap_callback)
            
            # Verify the loop was attempted
            mock_loop.run_until_complete.assert_called()
