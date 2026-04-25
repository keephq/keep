"""Tests for the SNMP Trap provider."""

from unittest.mock import MagicMock, patch

import pytest

from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import (_SEVERITY_MAP,
                                                        SnmpProvider,
                                                        SnmpProviderAuthConfig)


@pytest.fixture
def context_manager():
    ctx = MagicMock()
    ctx.tenant_id = "test-tenant"
    ctx.api_key = "test-api-key"
    return ctx


@pytest.fixture
def snmp_config():
    return ProviderConfig(
        description="Test SNMP Provider",
        authentication={
            "listen_port": 11162,
            "listen_address": "127.0.0.1",
            "community_string": "test-community",
        },
    )


@pytest.fixture
def snmp_provider(context_manager, snmp_config):
    return SnmpProvider(
        context_manager=context_manager,
        provider_id="test-snmp-provider",
        config=snmp_config,
    )


class TestSnmpProviderConfig:
    def test_validate_config(self, snmp_provider):
        assert snmp_provider.authentication_config.listen_port == 11162
        assert snmp_provider.authentication_config.listen_address == "127.0.0.1"
        assert snmp_provider.authentication_config.community_string == "test-community"

    def test_default_config(self):
        cfg = SnmpProviderAuthConfig()
        assert cfg.listen_port == 162
        assert cfg.listen_address == "0.0.0.0"
        assert cfg.community_string == "public"

    def test_status_not_initialized(self, snmp_provider):
        status = snmp_provider.status()
        assert status["status"] == "not-initialized"
        assert status["error"] == ""


class TestSnmpProviderAlertConversion:
    def test_varbinds_to_alert_basic(self, snmp_provider):
        """Test converting basic varbinds to an alert dict."""
        # Create mock OID and value objects
        trap_oid = MagicMock()
        trap_oid.__str__ = lambda s: "1.3.6.1.6.3.1.1.4.1.0"

        trap_val = MagicMock()
        trap_val.prettyPrint.return_value = "1.3.6.1.4.1.99999.1"

        data_oid = MagicMock()
        data_oid.__str__ = lambda s: "1.3.6.1.4.1.99999.2.1"

        data_val = MagicMock()
        data_val.prettyPrint.return_value = "CPU temperature critical"

        # Mock OID resolution
        snmp_provider._mib_view = MagicMock()

        def resolve_side_effect(oid):
            oid_str = str(oid)
            if oid_str == "1.3.6.1.6.3.1.1.4.1.0":
                return ("SNMPv2-MIB", "snmpTrapOID", (0,))
            if oid_str == "1.3.6.1.4.1.99999.1":
                return ("CUSTOM-MIB", "cpuTempCritical", ())
            if oid_str == "1.3.6.1.4.1.99999.2.1":
                return ("CUSTOM-MIB", "cpuTempValue", ())
            return ("", str(oid), ())

        snmp_provider._mib_view.getNodeName.side_effect = resolve_side_effect

        var_binds = [(trap_oid, trap_val), (data_oid, data_val)]
        alert = snmp_provider._varbinds_to_alert(var_binds)

        assert alert["name"] == "cpuTempCritical"
        assert "cpuTempValue" in alert["description"]
        assert alert["source"] == ["snmp"]
        assert alert["status"].value == "firing"

    def test_varbinds_no_trap_oid(self, snmp_provider):
        """When no snmpTrapOID is present, default name is used."""
        data_oid = MagicMock()
        data_oid.__str__ = lambda s: "1.3.6.1.4.1.99999.2.1"

        data_val = MagicMock()
        data_val.prettyPrint.return_value = "some value"

        snmp_provider._mib_view = MagicMock()
        snmp_provider._mib_view.getNodeName.side_effect = lambda oid: (
            "",
            str(oid),
            (),
        )

        alert = snmp_provider._varbinds_to_alert([(data_oid, data_val)])
        assert alert["name"] == "snmpTrap"

    def test_severity_mapping(self):
        """Known trap types map to expected severities."""
        assert _SEVERITY_MAP["linkDown"].value == ("high", 4)
        assert _SEVERITY_MAP["linkUp"].value == ("info", 2)
        assert _SEVERITY_MAP["coldStart"].value == ("warning", 3)


class TestSnmpProviderConsumer:
    def test_is_consumer(self, snmp_provider):
        """The provider should be recognized as a consumer."""
        assert snmp_provider.is_consumer is True

    def test_stop_consume(self, snmp_provider):
        """stop_consume should set the flag to False."""
        snmp_provider.consume = True
        snmp_provider._loop = MagicMock()
        snmp_provider._loop.is_running.return_value = True
        snmp_provider.stop_consume()
        assert snmp_provider.consume is False
        snmp_provider._loop.call_soon_threadsafe.assert_called_once()

    @patch("keep.providers.snmp_provider.snmp_provider.engine")
    @patch("keep.providers.snmp_provider.snmp_provider.snmp_config")
    @patch("keep.providers.snmp_provider.snmp_provider.udp")
    @patch("keep.providers.snmp_provider.snmp_provider.ntfrcv")
    def test_trap_callback_pushes_alert(
        self, mock_ntfrcv, mock_udp, mock_snmp_config, mock_engine, snmp_provider
    ):
        """The trap callback should call _push_alert."""
        snmp_provider._mib_view = MagicMock()
        snmp_provider._mib_view.getNodeName.side_effect = lambda oid: (
            "",
            str(oid),
            (),
        )

        with patch.object(snmp_provider, "_push_alert") as mock_push:
            snmp_provider._trap_callback(
                snmp_engine=MagicMock(),
                state_reference=None,
                context_engine_id=None,
                context_name=None,
                var_binds=[],
                cb_ctx=None,
            )
            mock_push.assert_called_once()
