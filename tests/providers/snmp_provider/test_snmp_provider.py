import json

import pytest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


def test_parse_json_bytes_array_wraps():
    body = json.dumps([{"trap_oid": "1.2.3", "agent_address": "10.0.0.1"}]).encode()
    out = SnmpProvider.parse_event_raw_body(body)
    assert out == {"snmp_traps": [{"trap_oid": "1.2.3", "agent_address": "10.0.0.1"}]}


def test_format_alert_single_link_down():
    event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "agent_address": "192.0.2.5",
        "hostname": "gw1",
        "message": "eth1 down",
    }
    alert = SnmpProvider._format_alert(event, None)
    assert isinstance(alert, AlertDto)
    assert "1.3.6.1.6.3.1.1.5.3" in alert.name or alert.labels.get("trap_oid")
    assert alert.message == "eth1 down"
    assert alert.status == AlertStatus.FIRING
    assert alert.severity == AlertSeverity.HIGH
    assert alert.host == "gw1"
    assert alert.source == ["snmp"]


def test_format_alert_batch():
    raw = {
        "snmp_traps": [
            {"trapOid": "1.3.6.1.6.3.1.1.5.1", "agentAddress": "192.0.2.1"},
            {"trap_oid": "1.3.6.1.6.3.1.1.5.4", "agent_address": "192.0.2.2"},
        ]
    }
    alerts = SnmpProvider._format_alert(raw, None)
    assert isinstance(alerts, list)
    assert len(alerts) == 2
    assert alerts[0].labels.get("trap_oid") == "1.3.6.1.6.3.1.1.5.1"
    assert alerts[1].labels.get("trap_oid") == "1.3.6.1.6.3.1.1.5.4"


def test_format_alert_explicit_severity_string():
    event = {
        "trap_oid": "1.3.6.1.4.1.99999.0.1",
        "agent_address": "10.0.0.2",
        "severity": "critical",
        "status": "firing",
    }
    alert = SnmpProvider._format_alert(event, None)
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.status == AlertStatus.FIRING


@pytest.mark.parametrize(
    "suffix,expected",
    [
        ("1", AlertSeverity.INFO),
        ("3", AlertSeverity.HIGH),
        ("4", AlertSeverity.INFO),
    ],
)
def test_severity_oid_map(suffix, expected):
    oid = f"1.3.6.1.6.3.1.1.5.{suffix}"
    assert SnmpProvider._severity_for_oid(oid) == expected


def test_severity_oid_enterprise_not_std_mib_prefix():
    """OIDs that end in .5.<n> but are NOT snmpTrapOID under 1.3.6.1.6.3.1.1.5.* must stay INFO."""
    assert (
        SnmpProvider._severity_for_oid("1.2.3.4.5.3") == AlertSeverity.INFO
    )


def test_format_alert_traps_must_be_list():
    with pytest.raises(ValueError, match="traps must be a list"):
        SnmpProvider._format_alert({"traps": "not-a-list"}, None)


def test_severity_int_out_of_range_falls_back_to_oid():
    event = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "agent_address": "10.0.0.1",
        "severity": 99,
    }
    alert = SnmpProvider._format_alert(event, None)
    assert alert.severity == AlertSeverity.HIGH


def test_severity_float_integer_json():
    event = {
        "trap_oid": "1.3.6.1.4.1.1",
        "agent_address": "10.0.0.1",
        "severity": 4.0,
    }
    alert = SnmpProvider._format_alert(event, None)
    assert alert.severity == AlertSeverity.HIGH
