"""Tests for the SNMP Trap provider."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import (
    SnmpProvider,
    SnmpProviderAuthConfig,
    _GENERIC_TRAP_NAMES,
    _SEVERITY_MAP,
    _V2_TRAP_OIDS,
)


def _oid(value: str) -> MagicMock:
    """Create a mock OID object whose str() returns *value*."""
    m = MagicMock()
    m.__str__ = MagicMock(return_value=value)
    return m


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

    def test_dispose(self, snmp_provider):
        """dispose() is a no-op and must not raise."""
        snmp_provider.dispose()

    def test_status_not_initialized(self, snmp_provider):
        status = snmp_provider.status()
        assert status["status"] == "not-initialized"
        assert status["error"] == ""

    def test_status_listening(self, snmp_provider):
        snmp_provider._socket = MagicMock()
        snmp_provider.consume = True
        status = snmp_provider.status()
        assert status["status"] == "listening"

    def test_status_stopped(self, snmp_provider):
        snmp_provider._socket = MagicMock()
        snmp_provider.consume = False
        status = snmp_provider.status()
        assert status["status"] == "stopped"


class TestSnmpProviderAlertConversion:
    def test_decode_v2c_trap_basic(self, snmp_provider):
        """SNMPv2c varbinds with a snmpTrapOID produce a named alert."""
        snmp_provider._mib_view = None

        trap_oid_obj = _oid("1.3.6.1.6.3.1.1.4.1.0")
        trap_val = MagicMock()
        trap_val.prettyPrint.return_value = "1.3.6.1.6.3.1.1.5.3"

        data_oid = _oid("1.3.6.1.2.1.2.2.1.1.2")
        data_val = MagicMock()
        data_val.prettyPrint.return_value = "2"

        var_binds = [(trap_oid_obj, trap_val), (data_oid, data_val)]
        alert = snmp_provider._decode_v2c_trap(var_binds, "192.168.1.1")

        assert alert["name"] == "linkDown"
        assert alert["severity"] == AlertSeverity.HIGH
        assert alert["status"] == AlertStatus.FIRING
        assert alert["source"] == ["snmp"]
        assert "message" in alert
        assert "1.3.6.1.2.1.2.2.1.1.2" in alert["labels"]

    def test_decode_v2c_trap_no_trap_oid(self, snmp_provider):
        """When no snmpTrapOID varbind is present, default name is used."""
        snmp_provider._mib_view = None

        data_oid = _oid("1.3.6.1.4.1.99999.2.1")
        data_val = MagicMock()
        data_val.prettyPrint.return_value = "some value"

        alert = snmp_provider._decode_v2c_trap([(data_oid, data_val)], "10.0.0.1")
        assert alert["name"] == "snmpTrap"
        assert alert["service"] == "10.0.0.1"

    def test_decode_v2c_trap_with_source_address(self, snmp_provider):
        """snmpTrapAddress varbind overrides the UDP source."""
        snmp_provider._mib_view = None

        addr_oid = _oid("1.3.6.1.6.3.18.1.3.0")
        addr_val = MagicMock()
        addr_val.prettyPrint.return_value = "10.0.0.99"

        alert = snmp_provider._decode_v2c_trap([(addr_oid, addr_val)], "192.168.1.1")
        assert alert["service"] == "10.0.0.99"

    def test_decode_v2c_trap_sysuptime_label(self, snmp_provider):
        """sysUpTime is stored as a label but excluded from description."""
        snmp_provider._mib_view = None

        uptime_oid = _oid("1.3.6.1.2.1.1.3.0")
        uptime_val = MagicMock()
        uptime_val.prettyPrint.return_value = "12345"

        alert = snmp_provider._decode_v2c_trap([(uptime_oid, uptime_val)], "10.0.0.1")
        assert alert["labels"]["sysUpTime"] == "12345"
        assert "12345" not in alert["description"]

    def test_decode_v1_trap(self, snmp_provider):
        """SNMPv1 Trap-PDU fields map correctly to alert fields."""
        snmp_provider._mib_view = None

        p_mod = MagicMock()
        pdu = MagicMock()
        p_mod.apiTrapPDU.getGenericTrap.return_value = 2  # linkDown
        p_mod.apiTrapPDU.getSpecificTrap.return_value = 0
        p_mod.apiTrapPDU.getEnterprise.return_value = "1.3.6.1.4.1.99999"
        p_mod.apiTrapPDU.getAgentAddr.return_value = "10.0.0.5"
        p_mod.apiTrapPDU.getVarBinds.return_value = []

        alert = snmp_provider._decode_v1_trap(p_mod, pdu, ("192.168.1.1", 162))
        assert alert["name"] == "linkDown"
        assert alert["severity"] == AlertSeverity.HIGH
        assert alert["service"] == "10.0.0.5"
        assert "message" in alert

    def test_decode_v1_enterprise_specific_trap(self, snmp_provider):
        """Generic-trap 6 uses enterprise OID + specific-trap as name."""
        snmp_provider._mib_view = None

        p_mod = MagicMock()
        pdu = MagicMock()
        p_mod.apiTrapPDU.getGenericTrap.return_value = 6
        p_mod.apiTrapPDU.getSpecificTrap.return_value = 42
        p_mod.apiTrapPDU.getEnterprise.return_value = "1.3.6.1.4.1.99999"
        p_mod.apiTrapPDU.getAgentAddr.return_value = None
        p_mod.apiTrapPDU.getVarBinds.return_value = []

        alert = snmp_provider._decode_v1_trap(p_mod, pdu, ("192.168.1.1", 162))
        assert alert["name"] == "1.3.6.1.4.1.99999.42"
        assert alert["service"] == "192.168.1.1"

    def test_resolve_oid_with_mib(self, snmp_provider):
        """When MIB view is available, OIDs resolve to names."""
        snmp_provider._mib_view = MagicMock()
        snmp_provider._mib_view.getNodeName.return_value = (
            "IF-MIB",
            "ifDescr",
            (1,),
        )
        result = snmp_provider._resolve_oid("1.3.6.1.2.1.2.2.1.2.1")
        assert result == "ifDescr.1"

    def test_resolve_oid_without_mib(self, snmp_provider):
        """Without MIB view, raw OID string is returned."""
        snmp_provider._mib_view = None
        result = snmp_provider._resolve_oid("1.3.6.1.2.1.2.2.1.2.1")
        assert result == "1.3.6.1.2.1.2.2.1.2.1"

    def test_resolve_oid_mib_exception(self, snmp_provider):
        """MIB resolution failure falls back to raw OID."""
        snmp_provider._mib_view = MagicMock()
        snmp_provider._mib_view.getNodeName.side_effect = Exception("not found")
        result = snmp_provider._resolve_oid("1.3.6.1.999")
        assert result == "1.3.6.1.999"

    def test_decode_v1_trap_with_varbind_none_val(self, snmp_provider):
        """Varbinds where val is None produce empty-string values."""
        snmp_provider._mib_view = None

        oid_mock = _oid("1.3.6.1.4.1.99999.3")

        p_mod = MagicMock()
        pdu = MagicMock()
        p_mod.apiTrapPDU.getGenericTrap.return_value = 3  # linkUp
        p_mod.apiTrapPDU.getSpecificTrap.return_value = 0
        p_mod.apiTrapPDU.getEnterprise.return_value = "1.3.6.1.4.1.99999"
        p_mod.apiTrapPDU.getAgentAddr.return_value = "10.0.0.1"
        p_mod.apiTrapPDU.getVarBinds.return_value = [(oid_mock, None)]

        alert = snmp_provider._decode_v1_trap(p_mod, pdu, ("10.0.0.1", 162))
        assert alert["labels"]["1.3.6.1.4.1.99999.3"] == ""

    def test_decode_v2c_unknown_trap_oid_defaults_to_warning(self, snmp_provider):
        """Unknown trap OIDs fall back to WARNING severity."""
        snmp_provider._mib_view = None

        trap_oid = _oid("1.3.6.1.6.3.1.1.4.1.0")
        trap_val = MagicMock()
        trap_val.prettyPrint.return_value = "1.3.6.1.4.1.99999.999"

        alert = snmp_provider._decode_v2c_trap([(trap_oid, trap_val)], "10.0.0.1")
        assert alert["name"] == "1.3.6.1.4.1.99999.999"
        assert alert["severity"] == AlertSeverity.WARNING


class TestSnmpProviderSeverityMapping:
    def test_standard_trap_severities(self):
        assert _SEVERITY_MAP["linkDown"] == AlertSeverity.HIGH
        assert _SEVERITY_MAP["linkUp"] == AlertSeverity.INFO
        assert _SEVERITY_MAP["coldStart"] == AlertSeverity.WARNING
        assert _SEVERITY_MAP["warmStart"] == AlertSeverity.INFO
        assert _SEVERITY_MAP["authenticationFailure"] == AlertSeverity.WARNING
        assert _SEVERITY_MAP["egpNeighborLoss"] == AlertSeverity.HIGH

    def test_generic_trap_names_complete(self):
        assert len(_GENERIC_TRAP_NAMES) == 7
        assert _GENERIC_TRAP_NAMES[0] == "coldStart"
        assert _GENERIC_TRAP_NAMES[6] == "enterpriseSpecific"

    def test_v2_trap_oids_complete(self):
        assert _V2_TRAP_OIDS["1.3.6.1.6.3.1.1.5.3"] == "linkDown"
        assert _V2_TRAP_OIDS["1.3.6.1.6.3.1.1.5.4"] == "linkUp"


class TestSnmpProviderConsumer:
    def test_is_consumer(self, snmp_provider):
        assert snmp_provider.is_consumer is True

    def test_stop_consume_sets_flag(self, snmp_provider):
        snmp_provider.consume = True
        snmp_provider._socket = MagicMock()
        snmp_provider.stop_consume()
        assert snmp_provider.consume is False

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_stop_consume_closes_socket(self, mock_socket_cls, snmp_provider):
        mock_sock = MagicMock()
        snmp_provider.consume = True
        snmp_provider._socket = mock_sock
        snmp_provider.stop_consume()
        mock_sock.close.assert_called_once()

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_stop_consume_sends_wakeup(self, mock_socket_cls, snmp_provider):
        """stop_consume sends a wake-up packet to unblock recvfrom."""
        mock_sock = MagicMock()
        wake_sock = MagicMock()
        mock_socket_cls.return_value = wake_sock
        snmp_provider.consume = True
        snmp_provider._socket = mock_sock
        snmp_provider.stop_consume()
        wake_sock.sendto.assert_called_once_with(
            b"\x00", ("127.0.0.1", 11162)
        )
        wake_sock.close.assert_called_once()

    def test_stop_consume_no_socket(self, snmp_provider):
        """stop_consume is safe when socket is None."""
        snmp_provider.consume = True
        snmp_provider._socket = None
        snmp_provider.stop_consume()
        assert snmp_provider.consume is False

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_start_consume_bind_failure(self, mock_socket_cls, snmp_provider):
        """start_consume exits gracefully and resets state on bind failure."""
        mock_sock = MagicMock()
        mock_sock.bind.side_effect = OSError("Address in use")
        mock_socket_cls.return_value = mock_sock

        snmp_provider.start_consume()

        mock_sock.close.assert_called()
        assert snmp_provider._socket is None
        assert snmp_provider.consume is False
        assert snmp_provider.err != ""

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_start_consume_processes_trap(self, mock_socket_cls, snmp_provider):
        """start_consume receives data and calls _push_alert."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        call_count = 0

        def recvfrom_side_effect(bufsize):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (b"\x30\x00", ("10.0.0.1", 162))
            snmp_provider.consume = False
            raise socket.timeout

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        with patch.object(
            snmp_provider, "_decode_trap", return_value={"name": "test"}
        ) as mock_decode:
            with patch.object(snmp_provider, "_push_alert") as mock_push:
                with patch.object(snmp_provider, "_init_mib_view"):
                    snmp_provider.start_consume()

                    mock_decode.assert_called_once_with(b"\x30\x00", ("10.0.0.1", 162))
                    mock_push.assert_called_once_with({"name": "test"})

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_start_consume_skips_none_alerts(self, mock_socket_cls, snmp_provider):
        """Traps that decode to None are not pushed."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        call_count = 0

        def recvfrom_side_effect(bufsize):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (b"\x30\x00", ("10.0.0.1", 162))
            snmp_provider.consume = False
            raise socket.timeout

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        with patch.object(snmp_provider, "_decode_trap", return_value=None):
            with patch.object(snmp_provider, "_push_alert") as mock_push:
                with patch.object(snmp_provider, "_init_mib_view"):
                    snmp_provider.start_consume()
                    mock_push.assert_not_called()

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_start_consume_handles_decode_exception(
        self, mock_socket_cls, snmp_provider
    ):
        """Exceptions in _decode_trap do not crash the consumer loop."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        call_count = 0

        def recvfrom_side_effect(bufsize):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (b"\x30\x00", ("10.0.0.1", 162))
            snmp_provider.consume = False
            raise socket.timeout

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        with patch.object(
            snmp_provider,
            "_decode_trap",
            side_effect=Exception("parse error"),
        ):
            with patch.object(snmp_provider, "_push_alert") as mock_push:
                with patch.object(snmp_provider, "_init_mib_view"):
                    snmp_provider.start_consume()
                    mock_push.assert_not_called()

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_start_consume_ignores_tiny_packets(self, mock_socket_cls, snmp_provider):
        """Packets smaller than 2 bytes (e.g. wake-up signals) are silently discarded."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        call_count = 0

        def recvfrom_side_effect(bufsize):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (b"\x00", ("127.0.0.1", 12345))
            snmp_provider.consume = False
            raise socket.timeout

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        with patch.object(snmp_provider, "_decode_trap") as mock_decode:
            with patch.object(snmp_provider, "_push_alert") as mock_push:
                with patch.object(snmp_provider, "_init_mib_view"):
                    snmp_provider.start_consume()
                    mock_decode.assert_not_called()
                    mock_push.assert_not_called()


class TestSnmpProviderTrapDecoding:
    @patch("keep.providers.snmp_provider.snmp_provider.ber_decoder")
    @patch("keep.providers.snmp_provider.snmp_provider.snmp_api")
    def test_decode_trap_wrong_community(self, mock_snmp_api, mock_ber, snmp_provider):
        """Traps with wrong community string return None."""
        mock_snmp_api.decodeMessageVersion.return_value = 1
        mock_snmp_api.protoModules = {1: MagicMock()}

        p_mod = mock_snmp_api.protoModules[1]
        mock_msg = MagicMock()
        mock_ber.decode.return_value = (mock_msg, b"")
        p_mod.apiMessage.getCommunity.return_value = "wrong-community"

        result = snmp_provider._decode_trap(b"\x30\x00", ("10.0.0.1", 162))
        assert result is None

    @patch("keep.providers.snmp_provider.snmp_provider.ber_decoder")
    @patch("keep.providers.snmp_provider.snmp_provider.snmp_api")
    def test_decode_trap_unsupported_version(
        self, mock_snmp_api, mock_ber, snmp_provider
    ):
        """Unsupported SNMP version returns None."""
        mock_snmp_api.decodeMessageVersion.return_value = 99
        mock_snmp_api.protoModules = {0: MagicMock(), 1: MagicMock()}

        result = snmp_provider._decode_trap(b"\x30\x00", ("10.0.0.1", 162))
        assert result is None

    @patch("keep.providers.snmp_provider.snmp_provider.ber_decoder")
    @patch("keep.providers.snmp_provider.snmp_provider.snmp_api")
    def test_decode_trap_ber_failure(self, mock_snmp_api, mock_ber, snmp_provider):
        """BER decode failure returns None."""
        mock_snmp_api.decodeMessageVersion.return_value = 1
        mock_snmp_api.protoModules = {1: MagicMock()}
        mock_ber.decode.side_effect = Exception("bad data")

        result = snmp_provider._decode_trap(b"\xff\xff", ("10.0.0.1", 162))
        assert result is None

    @patch("keep.providers.snmp_provider.snmp_provider.ber_decoder")
    @patch("keep.providers.snmp_provider.snmp_provider.snmp_api")
    def test_decode_trap_invalid_version_bytes(
        self, mock_snmp_api, mock_ber, snmp_provider
    ):
        """Garbled version bytes return None."""
        mock_snmp_api.decodeMessageVersion.side_effect = Exception("bad")

        result = snmp_provider._decode_trap(b"\xff", ("10.0.0.1", 162))
        assert result is None

    @patch("keep.providers.snmp_provider.snmp_provider.ber_decoder")
    @patch("keep.providers.snmp_provider.snmp_provider.snmp_api")
    def test_decode_trap_ignores_non_trap_v2c_pdu(
        self, mock_snmp_api, mock_ber, snmp_provider
    ):
        """Non-trap v2c PDUs (GET/RESPONSE) are ignored."""
        mock_snmp_api.decodeMessageVersion.return_value = 1
        mock_snmp_api.protoModules = {1: MagicMock()}

        p_mod = mock_snmp_api.protoModules[1]
        mock_msg = MagicMock()
        mock_ber.decode.return_value = (mock_msg, b"")
        p_mod.apiMessage.getCommunity.return_value = "test-community"

        mock_pdu = MagicMock()
        p_mod.apiMessage.getPDU.return_value = mock_pdu
        # Not a v1 TrapPDU
        mock_pdu.isSameTypeWith.return_value = False
        # Not a v2c trap or inform either
        p_mod.SNMPv2TrapPDU = None
        p_mod.InformRequestPDU = None

        result = snmp_provider._decode_trap(b"\x30\x00", ("10.0.0.1", 162))
        assert result is None


class TestSnmpProviderScopes:
    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_validate_scopes_success(self, mock_socket_cls, snmp_provider):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        scopes = snmp_provider.validate_scopes()
        assert scopes["receive_traps"] is True
        mock_sock.close.assert_called_once()

    @patch("keep.providers.snmp_provider.snmp_provider.socket.socket")
    def test_validate_scopes_bind_failure(self, mock_socket_cls, snmp_provider):
        mock_sock = MagicMock()
        mock_sock.bind.side_effect = OSError("Address in use")
        mock_socket_cls.return_value = mock_sock

        scopes = snmp_provider.validate_scopes()
        assert isinstance(scopes["receive_traps"], str)
        assert "Cannot bind" in scopes["receive_traps"]
        mock_sock.close.assert_called_once()


class TestSnmpProviderFormatAlert:
    def test_format_single_alert(self):
        event = {
            "name": "linkDown",
            "description": "GigabitEthernet0/1 down",
            "message": "GigabitEthernet0/1 down",
            "status": "firing",
            "severity": "high",
            "source": ["snmp"],
            "service": "10.0.0.1",
            "labels": {"ifIndex": "2"},
        }
        result = SnmpProvider._format_alert(event)
        assert isinstance(result, AlertDto)
        assert result.name == "linkDown"
        assert result.severity == AlertSeverity.HIGH.value
        assert result.status == AlertStatus.FIRING.value
        assert result.source == ["snmp"]
        assert result.service == "10.0.0.1"
        assert result.labels == {"ifIndex": "2"}

    def test_format_alert_list(self):
        events = [
            {"name": "coldStart", "status": "firing", "severity": "warning"},
            {"name": "linkUp", "status": "firing", "severity": "info"},
        ]
        result = SnmpProvider._format_alert(events)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].name == "coldStart"
        assert result[1].name == "linkUp"

    def test_format_alert_defaults(self):
        result = SnmpProvider._format_alert({})
        assert isinstance(result, AlertDto)
        assert result.name == "SNMP Trap"
        assert result.severity == AlertSeverity.INFO.value
        assert result.status == AlertStatus.FIRING.value
        assert result.source == ["snmp"]

    def test_format_alert_enum_passthrough(self):
        """When severity/status are already enums, pass them through."""
        event = {
            "name": "test",
            "severity": AlertSeverity.CRITICAL,
            "status": AlertStatus.RESOLVED,
        }
        result = SnmpProvider._format_alert(event)
        assert result.severity == AlertSeverity.CRITICAL.value
        assert result.status == AlertStatus.RESOLVED.value
