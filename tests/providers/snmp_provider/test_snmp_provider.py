"""Tests for SNMP trap ingestion provider (keephq/keep#2112)."""

from keep.providers.snmp_provider.snmp_utils import format_trap_alert


def test_format_trap_alert_extracts_snmp_trap_oid():
    class Oid:
        def __init__(self, s: str):
            self._s = s

        def prettyPrint(self):
            return self._s

    oid_trap = Oid("1.3.6.1.6.3.1.1.4.1.0")
    val_enterprise = Oid("1.3.6.1.4.1.99.2.3")
    oid_uptime = Oid("1.3.6.1.2.1.1.3.0")
    val_uptime = Oid("12345")

    alert = format_trap_alert([(oid_trap, val_enterprise), (oid_uptime, val_uptime)])

    assert alert["labels"]["trap_oid"] == "1.3.6.1.4.1.99.2.3"
    assert "1.3.6.1.4.1.99.2.3" in alert["message"]
    assert alert["status"].value == "firing"
    assert alert["fingerprint"]


def test_format_trap_alert_fallback_name_when_no_trap_oid_varbind():
    class Oid:
        def __init__(self, s: str):
            self._s = s

        def prettyPrint(self):
            return self._s

    alert = format_trap_alert([(Oid("1.2.3.4"), Oid("0"))])
    assert alert["name"]
    assert alert["message"]
