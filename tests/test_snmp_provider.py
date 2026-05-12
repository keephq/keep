from unittest.mock import MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


def _length(value: bytes) -> bytes:
    if len(value) < 0x80:
        return bytes([len(value)])
    encoded = len(value).to_bytes((len(value).bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _length(value) + value


def _seq(*values: bytes) -> bytes:
    return _tlv(0x30, b"".join(values))


def _integer(value: int) -> bytes:
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw
    return _tlv(0x02, raw)


def _octet(value: str) -> bytes:
    return _tlv(0x04, value.encode())


def _ip(value: str) -> bytes:
    return _tlv(0x40, bytes(int(part) for part in value.split(".")))


def _timeticks(value: int) -> bytes:
    return _tlv(0x43, value.to_bytes((value.bit_length() + 7) // 8 or 1, "big"))


def _oid(value: str) -> bytes:
    parts = [int(part) for part in value.split(".")]
    encoded = bytes([parts[0] * 40 + parts[1]])
    for part in parts[2:]:
        groups = [part & 0x7F]
        part >>= 7
        while part:
            groups.insert(0, part & 0x7F)
            part >>= 7
        encoded += bytes(group | 0x80 for group in groups[:-1])
        encoded += bytes([groups[-1]])
    return _tlv(0x06, encoded)


def _varbind(oid: str, value: bytes) -> bytes:
    return _seq(_oid(oid), value)


def _v2_link_down_packet() -> bytes:
    varbinds = _seq(
        _varbind("1.3.6.1.2.1.1.3.0", _timeticks(123)),
        _varbind(
            SnmpProvider.SNMP_TRAP_OID_VARBIND,
            _oid("1.3.6.1.6.3.1.1.5.3"),
        ),
        _varbind("1.3.6.1.2.1.2.2.1.2", _octet("eth0")),
    )
    pdu = _tlv(0xA7, _integer(1) + _integer(0) + _integer(0) + varbinds)
    return _seq(_integer(1), _octet("public"), pdu)


def _v1_auth_failure_packet() -> bytes:
    pdu = _tlv(
        0xA4,
        _oid("1.3.6.1.4.1.8072")
        + _ip("192.0.2.10")
        + _integer(4)
        + _integer(0)
        + _timeticks(456)
        + _seq(_varbind("1.3.6.1.2.1.1.5.0", _octet("router-1"))),
    )
    return _seq(_integer(0), _octet("public"), pdu)


def test_v2c_link_down_trap_maps_to_firing_critical_alert():
    alert = SnmpProvider._alert_from_datagram(_v2_link_down_packet(), "10.0.0.5")

    assert alert.name == "SNMP linkDown from 10.0.0.5"
    assert alert.status == "firing"
    assert alert.severity == "critical"
    assert alert.source == ["snmp"]
    assert alert.labels["trap_oid"] == "1.3.6.1.6.3.1.1.5.3"
    assert alert.labels["resource"] == "eth0"
    assert alert.fingerprint == "snmp:10.0.0.5:1.3.6.1.6.3.1.1.5.3:eth0"


def test_v1_authentication_failure_trap_maps_to_warning_alert():
    alert = SnmpProvider._alert_from_datagram(_v1_auth_failure_packet(), "192.0.2.10")

    assert alert.name == "SNMP authenticationFailure from 192.0.2.10"
    assert alert.status == "firing"
    assert alert.severity == "warning"
    assert alert.labels["snmp_version"] == "v1"
    assert alert.labels["resource"] == "router-1"


def test_webhook_payload_formatting_supports_trap_forwarders():
    alert = SnmpProvider._format_alert(
        {
            "source_ip": "198.51.100.7",
            "trap_name": "linkUp",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "varbinds": [{"oid": "1.3.6.1.2.1.2.2.1.2", "value": "ge-0/0/1"}],
        }
    )

    assert alert.status == "resolved"
    assert alert.severity == "info"
    assert alert.labels["resource"] == "ge-0/0/1"


def test_consumer_queues_alerts_before_pushing_to_keep():
    context_manager = ContextManager(
        tenant_id="tenant-id",
        workflow_id="workflow-id",
    )
    context_manager._api_key = "test-api-key"

    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-test",
        config=ProviderConfig(
            authentication={
                "listen_port": 0,
                "queue_size": 10,
            }
        ),
    )
    provider.consume = True
    provider._push_alert = MagicMock()

    provider._enqueue_alert({"name": "queued", "status": "firing", "severity": "info"})
    provider.consume = False
    provider._enqueue_sentinel()
    provider._alert_worker()

    provider._push_alert.assert_called_once_with(
        {"name": "queued", "status": "firing", "severity": "info"}
    )
