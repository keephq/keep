import pytest
from unittest.mock import MagicMock, patch
import json
import hashlib

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus


class TestSnmpProvider:
    @pytest.fixture
    def context_manager(self):
        return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")

    @pytest.fixture
    def provider(self, context_manager):
        config = ProviderConfig(
            authentication={
                "host": "localhost",
                "port": 161,
                "community": "public",
                "oids": "1.3.6.1.2.1.1.1.0, 1.3.6.1.2.1.1.3.0",
                "trap_port": 1162,
            }
        )
        return SnmpProvider(context_manager, "test_snmp", config)

    def test_validate_config(self, provider):
        assert provider.authentication_config.host == "localhost"
        assert provider.authentication_config.port == 161
        assert provider.authentication_config.community == "public"
        assert provider.authentication_config.oids == "1.3.6.1.2.1.1.1.0, 1.3.6.1.2.1.1.3.0"

    def test_format_alert(self, provider):
        # Sample var_binds mimicking trap reception
        raw_trap = {
            "1.3.6.1.2.1.1.3.0": "123456",
            "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.3",  # linkDown
            "1.3.6.1.2.1.2.2.1.1.1": "1"
        }
        
        alerts = provider._format_alert(raw_trap)
        assert not isinstance(alerts, list) # returns single dict if not list
        assert alerts.name == "SNMP Trap: 1.3.6.1.6.3.1.1.5.3"
        assert alerts.severity == AlertSeverity.HIGH
        assert alerts.status == AlertStatus.FIRING
        assert alerts.payload["1.3.6.1.2.1.2.2.1.1.1"] == "1"

    @patch("keep.providers.snmp_provider.snmp_provider.getCmd")
    def test_fetch_metrics_success(self, mock_get_cmd, provider):
        # Mock getCmd response
        mock_var_binds = [
            (MagicMock(prettyPrint=lambda: "1.3.6.1.2.1.1.1.0"), MagicMock(prettyPrint=lambda: "System Description")),
            (MagicMock(prettyPrint=lambda: "1.3.6.1.2.1.1.3.0"), MagicMock(prettyPrint=lambda: "987654"))
        ]
        # Return iterator
        mock_get_cmd.return_value = iter([(None, None, 0, mock_var_binds)])
        
        metrics = provider.fetch_metrics(["1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.3.0"])
        assert metrics == {
            "1.3.6.1.2.1.1.1.0": "System Description",
            "1.3.6.1.2.1.1.3.0": "987654"
        }

    @patch("keep.providers.snmp_provider.snmp_provider.getCmd")
    def test_fetch_metrics_timeout(self, mock_get_cmd, provider):
        # Mock timeout error
        mock_get_cmd.return_value = iter([("No SNMP response received before timeout", None, 0, [])])
        
        with pytest.raises(TimeoutError) as excinfo:
            provider.fetch_metrics(["1.3.6.1.2.1.1.1.0"])
        
        assert "timeout reaching" in str(excinfo.value)

    @patch("keep.providers.snmp_provider.snmp_provider.getCmd")
    def test_query(self, mock_get_cmd, provider):
        # Mock getCmd response
        mock_var_binds = [
            (MagicMock(prettyPrint=lambda: "1.3.6.1.2.1.1.1.0"), MagicMock(prettyPrint=lambda: "System Description"))
        ]
        mock_get_cmd.return_value = iter([(None, None, 0, mock_var_binds)])
        
        alerts = provider._query()
        assert len(alerts) == 1
        assert alerts[0].name == "SNMP OID 1.3.6.1.2.1.1.1.0"
        assert alerts[0].payload["value"] == "System Description"

