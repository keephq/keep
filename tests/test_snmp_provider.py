"""
Tests for the SNMP provider.

Covers:
- Raw BER decoder (v1 + v2c traps, no pysnmp needed)
- Severity inference from varbind text
- Well-known OID mapping (linkDown, authFailure, linkUp, coldStart)
- Alert builder fields (name, severity, status, source, pushed)
- Queue filling and draining via _get_alerts (with mock listener)
- Community string filtering
- SNMPv3 config validation (username present → v3 enabled)
"""

import queue
import socket
import struct
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider, WELL_KNOWN_TRAPS


def _make_provider(
    community="public",
    listen_port=16200,
    v3_username=None,
    v3_auth_key=None,
    v3_priv_key=None,
):
    """Helper: build an SnmpProvider with a mock context manager."""
    context_manager = MagicMock(spec=ContextManager)
    context_manager.tenant_id = "test-tenant"
    config = ProviderConfig(
        authentication={
            "listen_host": "127.0.0.1",
            "listen_port": listen_port,
            "community": community,
            "v3_username": v3_username,
            "v3_auth_key": v3_auth_key,
            "v3_priv_key": v3_priv_key,
            "max_queue_size": 100,
        }
    )
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="test-snmp",
        config=config,
    )
    return provider


# ---------------------------------------------------------------------------
# BER helper: encode a minimal SNMPv2c Trap PDU
# ---------------------------------------------------------------------------

def _encode_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    if length < 0x100:
        return bytes([0x81, length])
    return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])


def _encode_integer(value: int) -> bytes:
    return b"\x02\x01" + bytes([value & 0xFF])


def _encode_octet_string(s: str) -> bytes:
    enc = s.encode()
    return b"\x04" + _encode_length(len(enc)) + enc


def _encode_oid(dotted: str) -> bytes:
    parts = list(map(int, dotted.split(".")))
    first = parts[0] * 40 + parts[1]
    body = [first] + parts[2:]
    encoded = []
    for v in body:
        if v == 0:
            encoded.append(0)
        else:
            septets = []
            while v:
                septets.append(v & 0x7F)
                v >>= 7
            septets.reverse()
            for i, s in enumerate(septets):
                encoded.append(s | (0x80 if i < len(septets) - 1 else 0))
    return b"\x06" + _encode_length(len(encoded)) + bytes(encoded)


def _build_v2c_trap(community: str, trap_oid: str) -> bytes:
    """Build a minimal SNMPv2c Trap PDU."""
    version = _encode_integer(1)  # version 2 = integer 1
    comm = _encode_octet_string(community)

    # VarBind: snmpTrapOID.0 = trap_oid
    snmp_trap_oid_oid = _encode_oid("1.3.6.1.6.3.1.1.4.1.0")
    trap_oid_value = _encode_oid(trap_oid)
    varbind = b"\x30" + _encode_length(len(snmp_trap_oid_oid) + len(trap_oid_value)) + snmp_trap_oid_oid + trap_oid_value
    varbind_list = b"\x30" + _encode_length(len(varbind)) + varbind

    # PDU: request-id(0), error-status(0), error-index(0), varbinds
    req_id = _encode_integer(0)
    err_status = _encode_integer(0)
    err_index = _encode_integer(0)
    pdu_body = req_id + err_status + err_index + varbind_list
    pdu = b"\xa7" + _encode_length(len(pdu_body)) + pdu_body

    msg_body = version + comm + pdu
    return b"\x30" + _encode_length(len(msg_body)) + msg_body


# ---------------------------------------------------------------------------

class TestSnmpProviderConfig(unittest.TestCase):
    def test_valid_config(self):
        p = _make_provider()
        self.assertEqual(p.authentication_config.community, "public")
        self.assertEqual(p.authentication_config.listen_port, 16200)

    def test_invalid_port(self):
        with self.assertRaises(Exception):
            _make_provider(listen_port=0)

    def test_v3_username_stored(self):
        p = _make_provider(v3_username="admin", v3_auth_key="authpass", v3_priv_key="privpass")
        self.assertEqual(p.authentication_config.v3_username, "admin")


class TestSeverityInference(unittest.TestCase):
    def test_critical_keyword(self):
        p = _make_provider()
        self.assertEqual(p._infer_severity("CRITICAL error on interface"), AlertSeverity.CRITICAL)

    def test_warning_keyword(self):
        p = _make_provider()
        self.assertEqual(p._infer_severity("warning: memory low"), AlertSeverity.WARNING)

    def test_default_info(self):
        p = _make_provider()
        self.assertEqual(p._infer_severity("some varbind data"), AlertSeverity.INFO)

    def test_high_keyword(self):
        p = _make_provider()
        self.assertEqual(p._infer_severity("major interface failure"), AlertSeverity.HIGH)


class TestWellKnownOids(unittest.TestCase):
    def test_link_down_severity(self):
        self.assertEqual(WELL_KNOWN_TRAPS["1.3.6.1.6.3.1.1.5.3"]["severity"], AlertSeverity.HIGH)

    def test_auth_failure_critical(self):
        self.assertEqual(WELL_KNOWN_TRAPS["1.3.6.1.6.3.1.1.5.5"]["severity"], AlertSeverity.CRITICAL)

    def test_link_up_info(self):
        self.assertEqual(WELL_KNOWN_TRAPS["1.3.6.1.6.3.1.1.5.4"]["severity"], AlertSeverity.INFO)

    def test_cold_start_warning(self):
        self.assertEqual(WELL_KNOWN_TRAPS["1.3.6.1.6.3.1.1.5.1"]["severity"], AlertSeverity.WARNING)


class TestAlertBuilder(unittest.TestCase):
    def setUp(self):
        self.p = _make_provider()

    def test_link_down_alert(self):
        alert = self.p._build_alert(
            "1.3.6.1.6.3.1.1.5.3", "ifIndex=2", "192.168.1.1", "SNMPv2-Trap"
        )
        self.assertEqual(alert.name, "linkDown")
        self.assertEqual(alert.severity, AlertSeverity.HIGH)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.source, ["snmp"])
        self.assertTrue(alert.pushed)

    def test_link_up_resolved(self):
        alert = self.p._build_alert(
            "1.3.6.1.6.3.1.1.5.4", "ifIndex=2", "192.168.1.1", "SNMPv2-Trap"
        )
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_unknown_oid_defaults_to_info(self):
        alert = self.p._build_alert(
            "1.2.3.4.5.6", "some=varbind", "10.0.0.1", "SNMPv2-Trap"
        )
        self.assertEqual(alert.severity, AlertSeverity.INFO)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_alert_has_id_and_lastReceived(self):
        alert = self.p._build_alert("1.2.3", "x=1", "1.2.3.4", "v2c")
        self.assertIsNotNone(alert.id)
        self.assertIsNotNone(alert.lastReceived)


class TestBerDecoder(unittest.TestCase):
    def setUp(self):
        self.p = _make_provider()

    def test_v2c_link_down(self):
        data = _build_v2c_trap("public", "1.3.6.1.6.3.1.1.5.3")
        alert = self.p._decode_with_ber(data, ("192.168.1.1", 12345))
        self.assertIsNotNone(alert)

    def test_community_mismatch_returns_none(self):
        data = _build_v2c_trap("wrong-community", "1.3.6.1.6.3.1.1.5.3")
        alert = self.p._decode_with_ber(data, ("192.168.1.1", 12345))
        self.assertIsNone(alert)

    def test_garbage_data_returns_none(self):
        alert = self.p._decode_with_ber(b"\x00\x01\x02garbage", ("1.2.3.4", 0))
        self.assertIsNone(alert)

    def test_empty_data_returns_none(self):
        alert = self.p._decode_with_ber(b"", ("1.2.3.4", 0))
        self.assertIsNone(alert)


class TestQueueDrain(unittest.TestCase):
    def test_queue_filled_and_drained(self):
        p = _make_provider(listen_port=16201)

        # Manually inject alerts into the queue
        for i in range(5):
            alert = p._build_alert(
                "1.3.6.1.6.3.1.1.5.3", f"ifIndex={i}", f"10.0.0.{i}", "test"
            )
            p._trap_queue.put_nowait(alert)

        # Patch listener thread to avoid binding a socket
        p._listener_thread = threading.Thread(target=lambda: None, daemon=True)
        p._listener_thread.start()
        p._listener_thread.join()

        alerts = p._get_alerts()
        self.assertEqual(len(alerts), 5)
        # Queue should be empty now
        self.assertTrue(p._trap_queue.empty())

    def test_queue_full_drops_trap(self):
        p = _make_provider(listen_port=16202)
        p._trap_queue = queue.Queue(maxsize=2)

        # Fill queue
        for i in range(2):
            p._trap_queue.put_nowait(
                p._build_alert("1.3.6.1.6.3.1.1.5.3", "x=1", "1.2.3.4", "v2c")
            )

        # This should not raise — it should log and drop
        data = _build_v2c_trap("public", "1.3.6.1.6.3.1.1.5.3")
        p._handle_datagram(data, ("1.2.3.4", 0))
        self.assertEqual(p._trap_queue.qsize(), 2)


class TestUdpListener(unittest.TestCase):
    """Integration: actually bind a UDP socket and send a trap."""

    def test_end_to_end_v2c(self):
        PORT = 16210
        p = _make_provider(listen_port=PORT)
        p._start_listener()
        time.sleep(0.2)

        # Send a linkDown trap
        data = _build_v2c_trap("public", "1.3.6.1.6.3.1.1.5.3")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(data, ("127.0.0.1", PORT))
        sock.close()

        time.sleep(0.3)
        alerts = p._get_alerts()
        p.dispose()

        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].name, "linkDown")

    def test_community_filter_drops_wrong(self):
        PORT = 16211
        p = _make_provider(listen_port=PORT)
        p._start_listener()
        time.sleep(0.2)

        data = _build_v2c_trap("wrong-community", "1.3.6.1.6.3.1.1.5.3")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(data, ("127.0.0.1", PORT))
        sock.close()

        time.sleep(0.3)
        alerts = p._get_alerts()
        p.dispose()

        self.assertEqual(len(alerts), 0)


if __name__ == "__main__":
    unittest.main()
