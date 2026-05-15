"""
Tests for the SNMP Provider.

Covers:
- Provider discovery via ProvidersFactory
- Config validation (v1, v2c, v3 — happy and error paths)
- _format_alert mapping for all generic traps
- Custom oid_severity_map overrides
- Fingerprint stability
- Malformed trap resilience
- linkDown/linkUp resolution pairing
- start_consume integration test (UDP trap on port 1162)
- dispose idempotency
"""

import datetime
import hashlib
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_context_manager():
    ctx = MagicMock()
    ctx.tenant_id = "test-tenant"
    ctx.api_key = "test-api-key"
    return ctx


def _make_provider(ctx, auth_overrides=None):
    """Instantiate an SnmpProvider with the given auth config overrides."""
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    auth = {
        "snmp_version": "v2c",
        "listen_address": "127.0.0.1",
        "listen_port": 1162,
        "community_string": "public",
    }
    if auth_overrides:
        auth.update(auth_overrides)

    config = ProviderConfig(authentication=auth)
    provider = SnmpProvider(context_manager=ctx, provider_id="snmp-test", config=config)
    return provider


# ---------------------------------------------------------------------------
# 1. Provider loads via factory
# ---------------------------------------------------------------------------


def test_provider_loads_via_factory():
    from keep.providers.providers_factory import ProvidersFactory

    provider_class = ProvidersFactory.get_provider_class("snmp")
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    assert provider_class is SnmpProvider


# ---------------------------------------------------------------------------
# 2. validate_config — happy paths (parametrize v1, v2c, v3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version,extra",
    [
        ("v1", {}),
        ("v2c", {}),
        (
            "v3",
            {
                "security_name": "testuser",
                "auth_protocol": "MD5",
                "auth_key": "authpass123",
                "priv_protocol": "DES",
                "priv_key": "privpass123",
            },
        ),
    ],
)
def test_validate_config_happy(mock_context_manager, version, extra):
    provider = _make_provider(mock_context_manager, {"snmp_version": version, **extra})
    assert provider.authentication_config.snmp_version == version


# ---------------------------------------------------------------------------
# 3. validate_config — v3 missing required fields
# ---------------------------------------------------------------------------


def test_validate_config_v3_missing_security_name(mock_context_manager):
    with pytest.raises(Exception, match="security_name"):
        _make_provider(mock_context_manager, {"snmp_version": "v3"})


def test_validate_config_v3_missing_auth_key(mock_context_manager):
    with pytest.raises(Exception, match="auth_key"):
        _make_provider(
            mock_context_manager,
            {
                "snmp_version": "v3",
                "security_name": "user1",
                "auth_protocol": "SHA",
            },
        )


def test_validate_config_v3_missing_priv_key(mock_context_manager):
    with pytest.raises(Exception, match="priv_key"):
        _make_provider(
            mock_context_manager,
            {
                "snmp_version": "v3",
                "security_name": "user1",
                "auth_protocol": "none",
                "priv_protocol": "AES",
            },
        )


def test_validate_config_invalid_version(mock_context_manager):
    with pytest.raises(Exception, match="Invalid snmp_version"):
        _make_provider(mock_context_manager, {"snmp_version": "v4"})


def test_validate_config_invalid_port(mock_context_manager):
    with pytest.raises(Exception, match="listen_port"):
        _make_provider(mock_context_manager, {"listen_port": 0})


# ---------------------------------------------------------------------------
# 4. _format_alert — all 6 generic traps severity mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "trap_oid,expected_severity,expected_name",
    [
        ("1.3.6.1.6.3.1.1.5.1", "info", "coldStart"),
        ("1.3.6.1.6.3.1.1.5.2", "info", "warmStart"),
        ("1.3.6.1.6.3.1.1.5.3", "critical", "linkDown"),
        ("1.3.6.1.6.3.1.1.5.4", "info", "linkUp"),
        ("1.3.6.1.6.3.1.1.5.5", "warning", "authenticationFailure"),
        ("1.3.6.1.6.3.1.1.5.6", "warning", "egpNeighborLoss"),
    ],
)
def test_format_alert_severity_mapping(trap_oid, expected_severity, expected_name):
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    event = {
        "trap_oid": trap_oid,
        "trap_name": expected_name,
        "snmp_version": "v2c",
        "source_address": "10.0.0.1",
        "source_port": 49152,
        "community": "***",
        "uptime": "12345",
        "varbinds": [],
        "raw_pdu": "",
        "received_at": "2026-05-14T12:00:00+00:00",
        "severity": expected_severity,
        "status": "firing",
        "ifIndex": None,
    }

    alert = SnmpProvider._format_alert(event)

    assert alert["name"] == expected_name
    assert alert["severity"] == expected_severity
    assert alert["source"] == ["snmp"]
    assert alert["lastReceived"] == "2026-05-14T12:00:00+00:00"


# ---------------------------------------------------------------------------
# 5. linkDown then linkUp — resolution pairing
# ---------------------------------------------------------------------------


def test_linkdown_linkup_resolution_pairing():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    base_event = {
        "snmp_version": "v2c",
        "source_address": "10.0.0.1",
        "source_port": 49152,
        "community": "***",
        "uptime": "12345",
        "varbinds": [],
        "raw_pdu": "",
        "received_at": "2026-05-14T12:00:00+00:00",
        "ifIndex": "5",
    }

    # linkDown event
    link_down = {
        **base_event,
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "trap_name": "linkDown",
        "severity": "critical",
        "status": "firing",
    }

    # linkUp event — same ifIndex
    link_up = {
        **base_event,
        "trap_oid": "1.3.6.1.6.3.1.1.5.4",
        "trap_name": "linkUp",
        "severity": "info",
        "status": "resolved",
    }

    alert_down = SnmpProvider._format_alert(link_down)
    alert_up = SnmpProvider._format_alert(link_up)

    assert alert_down["status"] == "firing"
    assert alert_up["status"] == "resolved"
    assert alert_down["severity"] == "critical"
    assert alert_up["severity"] == "info"

    # linkDown/linkUp on the same interface should share a lifecycle fingerprint
    assert alert_down["fingerprint"] == alert_up["fingerprint"]

    # But both include ifIndex in labels
    assert alert_down["labels"]["ifIndex"] == "5"
    assert alert_up["labels"]["ifIndex"] == "5"


# ---------------------------------------------------------------------------
# 6. Custom oid_severity_map override
# ---------------------------------------------------------------------------


def test_custom_oid_severity_map(mock_context_manager):
    provider = _make_provider(
        mock_context_manager,
        {"oid_severity_map": {"1.3.6.1.6.3.1.1.5.1": "critical"}},
    )

    severity = provider._get_severity("1.3.6.1.6.3.1.1.5.1")
    from keep.api.models.alert import AlertSeverity

    assert severity == AlertSeverity.CRITICAL


def test_custom_oid_severity_map_unknown_falls_back(mock_context_manager):
    provider = _make_provider(
        mock_context_manager,
        {"oid_severity_map": {"1.3.6.1.4.1.9999": "high"}},
    )

    severity = provider._get_severity("1.3.6.1.4.1.9999")
    from keep.api.models.alert import AlertSeverity

    assert severity == AlertSeverity.HIGH


# ---------------------------------------------------------------------------
# 7. Fingerprint stability
# ---------------------------------------------------------------------------


def test_fingerprint_stability():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "trap_name": "linkDown",
        "snmp_version": "v2c",
        "source_address": "10.0.0.1",
        "source_port": 49152,
        "community": "***",
        "uptime": "12345",
        "varbinds": [
            {"oid": "1.3.6.1.2.1.2.2.1.1.5", "type": "Integer32", "value": "5"}
        ],
        "raw_pdu": "",
        "received_at": "2026-05-14T12:00:00+00:00",
        "severity": "critical",
        "status": "firing",
        "ifIndex": "5",
    }

    alert1 = SnmpProvider._format_alert(event)
    alert2 = SnmpProvider._format_alert(event)

    # Same input -> same fingerprint
    assert alert1["fingerprint"] == alert2["fingerprint"]

    # Expected fingerprint value
    expected = hashlib.sha256("10.0.0.1|1.3.6.1.6.3.1.1.5.3|5".encode()).hexdigest()
    assert alert1["fingerprint"] == expected


def test_linkup_uses_linkdown_fingerprint():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.4",
        "trap_name": "linkUp",
        "snmp_version": "v2c",
        "source_address": "10.0.0.1",
        "source_port": 49152,
        "community": "***",
        "uptime": "12345",
        "varbinds": [],
        "raw_pdu": "",
        "received_at": "2026-05-14T12:00:00+00:00",
        "severity": "info",
        "status": "resolved",
        "ifIndex": "5",
    }

    alert = SnmpProvider._format_alert(event)
    expected = hashlib.sha256("10.0.0.1|1.3.6.1.6.3.1.1.5.3|5".encode()).hexdigest()
    assert alert["fingerprint"] == expected


def test_fingerprint_differs_with_different_ifindex():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    base_event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "trap_name": "linkDown",
        "snmp_version": "v2c",
        "source_address": "10.0.0.1",
        "source_port": 49152,
        "community": "***",
        "uptime": "12345",
        "varbinds": [],
        "raw_pdu": "",
        "received_at": "2026-05-14T12:00:00+00:00",
        "severity": "critical",
        "status": "firing",
    }

    event_if5 = {**base_event, "ifIndex": "5"}
    event_if10 = {**base_event, "ifIndex": "10"}

    fp5 = SnmpProvider._format_alert(event_if5)["fingerprint"]
    fp10 = SnmpProvider._format_alert(event_if10)["fingerprint"]

    assert fp5 != fp10


# ---------------------------------------------------------------------------
# 8. Malformed trap — no crash
# ---------------------------------------------------------------------------


def test_format_alert_malformed_no_crash():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    # Missing most fields
    event = {}
    alert = SnmpProvider._format_alert(event)

    assert alert["name"] == "SNMP trap unknown"
    assert alert["severity"] == "info"
    assert alert["source"] == ["snmp"]
    assert "fingerprint" in alert


def test_format_alert_junk_varbinds():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.1",
        "trap_name": "coldStart",
        "snmp_version": "v2c",
        "source_address": "10.0.0.1",
        "varbinds": [
            {"oid": None, "type": None, "value": None},
            "not-a-dict",
        ],
        "severity": "info",
        "status": "firing",
    }

    # Should not raise
    alert = SnmpProvider._format_alert(event)
    assert alert["name"] == "coldStart"


# ---------------------------------------------------------------------------
# 9. build_event methods
# ---------------------------------------------------------------------------


def test_build_event_v2c_v3(mock_context_manager):
    provider = _make_provider(mock_context_manager)

    from pysnmp.proto.rfc1902 import ObjectIdentifier, OctetString, Integer

    var_binds = [
        (
            ObjectIdentifier("1.3.6.1.6.3.1.1.4.1.0"),
            ObjectIdentifier("1.3.6.1.6.3.1.1.5.3"),
        ),
        (ObjectIdentifier("1.3.6.1.2.1.1.3.0"), Integer(123456)),
        (ObjectIdentifier("1.3.6.1.2.1.2.2.1.1.5"), Integer(5)),
    ]
    transport_address = ("10.0.0.1", 49152)

    event = provider._build_event_from_v2c_v3(
        var_binds=var_binds,
        transport_address=transport_address,
        snmp_version="v2c",
    )

    assert event["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
    assert event["trap_name"] == "linkDown"
    assert event["source_address"] == "10.0.0.1"
    assert event["snmp_version"] == "v2c"
    assert event["ifIndex"] == "5"
    assert event["status"] == "firing"  # linkDown is FIRING
    assert event["community"] == "***"  # community is redacted


def test_build_event_v2c_linkup_resolved(mock_context_manager):
    provider = _make_provider(mock_context_manager)

    from pysnmp.proto.rfc1902 import ObjectIdentifier, Integer

    var_binds = [
        (
            ObjectIdentifier("1.3.6.1.6.3.1.1.4.1.0"),
            ObjectIdentifier("1.3.6.1.6.3.1.1.5.4"),
        ),
        (ObjectIdentifier("1.3.6.1.2.1.1.3.0"), Integer(123456)),
        (ObjectIdentifier("1.3.6.1.2.1.2.2.1.1.5"), Integer(5)),
    ]
    transport_address = ("10.0.0.1", 49152)

    event = provider._build_event_from_v2c_v3(
        var_binds=var_binds,
        transport_address=transport_address,
        snmp_version="v2c",
    )

    assert event["trap_oid"] == "1.3.6.1.6.3.1.1.5.4"
    assert event["trap_name"] == "linkUp"
    assert event["status"] == "resolved"  # linkUp with ifIndex -> RESOLVED


# ---------------------------------------------------------------------------
# 10. Provider status and dispose
# ---------------------------------------------------------------------------


def test_status_default(mock_context_manager):
    provider = _make_provider(mock_context_manager)
    status = provider.status()
    assert status["status"] == "stopped"
    assert status["error"] == ""


def test_dispose_idempotent(mock_context_manager):
    provider = _make_provider(mock_context_manager)
    # dispose multiple times should not raise
    provider.dispose()
    provider.dispose()
    assert provider.status()["status"] == "stopped"


# ---------------------------------------------------------------------------
# 11. is_consumer property
# ---------------------------------------------------------------------------


def test_is_consumer(mock_context_manager):
    provider = _make_provider(mock_context_manager)
    assert provider.is_consumer is True


# ---------------------------------------------------------------------------
# 12. PROVIDER_DISPLAY_NAME and class attributes
# ---------------------------------------------------------------------------


def test_provider_class_attributes():
    from keep.providers.snmp_provider.snmp_provider import SnmpProvider

    assert SnmpProvider.PROVIDER_DISPLAY_NAME == "SNMP"
    assert "Monitoring" in SnmpProvider.PROVIDER_CATEGORY
    assert "alert" in SnmpProvider.PROVIDER_TAGS
    assert "queue" in SnmpProvider.PROVIDER_TAGS
    assert SnmpProvider.WEBHOOK_INSTALLATION_REQUIRED is False
    assert SnmpProvider.FINGERPRINT_FIELDS == [
        "source_address",
        "trap_oid",
        "ifIndex",
    ]


# ---------------------------------------------------------------------------
# 13. Integration test: start_consume with real UDP trap
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_start_consume_integration(mock_context_manager):
    """
    Spin up SnmpProvider on 127.0.0.1:1162, send a v2c linkDown trap
    using a pre-encoded BER SNMPv2c message via raw UDP, then assert
    that _push_alert was called with the expected dict.
    """
    import socket
    import threading
    import time

    provider = _make_provider(mock_context_manager)

    pushed_alerts = []

    def capture_push(alert):
        pushed_alerts.append(alert)

    provider._push_alert = capture_push

    # Start consume in a background thread
    consume_thread = threading.Thread(target=provider.start_consume, daemon=True)
    consume_thread.start()

    # Wait for listener to bind
    time.sleep(1.5)

    # Build a valid SNMPv2c trap message using pyasn1 BER encoding directly.
    # Structure: SEQUENCE { INTEGER 1, OCTET STRING "public", [7] IMPLICIT { ... } }
    from pyasn1.type import univ, tag
    from pyasn1.codec.ber import encoder as ber_encoder

    def encode_oid(oid_str):
        """Encode an OID string to BER bytes."""
        parts = [int(x) for x in oid_str.split(".")]
        first = 40 * parts[0] + parts[1]
        result = bytes([first])
        for p in parts[2:]:
            if p < 128:
                result += bytes([p])
            else:
                # multi-byte encoding
                chunks = []
                while p > 0:
                    chunks.append(p & 0x7F)
                    p >>= 7
                chunks.reverse()
                for i, c in enumerate(chunks):
                    if i < len(chunks) - 1:
                        result += bytes([c | 0x80])
                    else:
                        result += bytes([c])
        return result

    def tlv(tag_byte, value):
        """Build a TLV (tag-length-value) BER element."""
        length = len(value)
        if length < 128:
            return bytes([tag_byte, length]) + value
        elif length < 256:
            return bytes([tag_byte, 0x81, length]) + value
        else:
            return bytes([tag_byte, 0x82, (length >> 8) & 0xFF, length & 0xFF]) + value

    def oid_tlv(oid_str):
        return tlv(0x06, encode_oid(oid_str))

    def int_tlv(val):
        if val == 0:
            return bytes([0x02, 0x01, 0x00])
        # Simple positive integer encoding
        b = val.to_bytes((val.bit_length() + 8) // 8, "big", signed=True)
        return tlv(0x02, b)

    def timeticks_tlv(val):
        b = val.to_bytes((val.bit_length() + 8) // 8, "big", signed=False)
        return tlv(0x43, b)

    # Build varbinds
    # VarBind 1: sysUpTime.0 = 12345 (TimeTicks)
    vb1 = tlv(0x30, oid_tlv("1.3.6.1.2.1.1.3.0") + timeticks_tlv(12345))

    # VarBind 2: snmpTrapOID.0 = 1.3.6.1.6.3.1.1.5.3 (linkDown)
    vb2 = tlv(0x30, oid_tlv("1.3.6.1.6.3.1.1.4.1.0") + oid_tlv("1.3.6.1.6.3.1.1.5.3"))

    # VarBind 3: ifIndex.5 = 5 (INTEGER)
    vb3 = tlv(0x30, oid_tlv("1.3.6.1.2.1.2.2.1.1.5") + int_tlv(5))

    varbind_list = tlv(0x30, vb1 + vb2 + vb3)

    # SNMPv2-Trap-PDU: [7] IMPLICIT SEQUENCE { request-id, error-status, error-index, varbinds }
    pdu_body = int_tlv(0) + int_tlv(0) + int_tlv(0) + varbind_list
    # tag 0xA7 = context-specific, constructed, tag number 7
    trap_pdu = tlv(0xA7, pdu_body)

    # SNMPv2c Message: SEQUENCE { version=1, community="public", PDU }
    version = int_tlv(1)  # version 1 = v2c
    community = tlv(0x04, b"public")
    snmp_msg = tlv(0x30, version + community + trap_pdu)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(snmp_msg, ("127.0.0.1", 1162))
        sock.close()
    except Exception as e:
        provider.dispose()
        consume_thread.join(timeout=3)
        pytest.skip(f"Could not send trap: {e}")

    # Wait for processing
    time.sleep(2)

    # Stop the provider
    provider.dispose()
    consume_thread.join(timeout=5)

    # Verify alert was pushed
    assert (
        len(pushed_alerts) >= 1
    ), f"Expected at least 1 alert, got {len(pushed_alerts)}"
    alert = pushed_alerts[0]
    assert alert["source"] == ["snmp"]
    assert "fingerprint" in alert


# ---------------------------------------------------------------------------
# 14. V3 auth/priv protocol mapping
# ---------------------------------------------------------------------------


def test_auth_protocol_mapping(mock_context_manager):
    provider = _make_provider(
        mock_context_manager,
        {
            "snmp_version": "v3",
            "security_name": "user1",
            "auth_protocol": "MD5",
            "auth_key": "authpass123",
            "priv_protocol": "none",
        },
    )

    from pysnmp.entity import config as snmp_config

    assert provider._get_auth_protocol() == snmp_config.usmHMACMD5AuthProtocol
    assert provider._get_priv_protocol() == snmp_config.usmNoPrivProtocol


def test_auth_protocol_sha(mock_context_manager):
    provider = _make_provider(
        mock_context_manager,
        {
            "snmp_version": "v3",
            "security_name": "user1",
            "auth_protocol": "SHA",
            "auth_key": "authpass123",
            "priv_protocol": "DES",
            "priv_key": "privpass123",
        },
    )

    from pysnmp.entity import config as snmp_config

    assert provider._get_auth_protocol() == snmp_config.usmHMACSHAAuthProtocol
    assert provider._get_priv_protocol() == snmp_config.usmDESPrivProtocol


def test_auth_protocol_unknown_fallback(mock_context_manager):
    provider = _make_provider(
        mock_context_manager,
        {
            "snmp_version": "v3",
            "security_name": "user1",
            "auth_protocol": "BOGUS",
            "auth_key": "authpass123",
        },
    )

    from pysnmp.entity import config as snmp_config

    assert provider._get_auth_protocol() == snmp_config.usmNoAuthProtocol
