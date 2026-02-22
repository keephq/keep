"""
Tests for the SNMP Provider's alert formatting logic.

These tests exercise SnmpProvider._format_alert() directly — no database,
no HTTP, no mocking of Keep internals.  They are designed to run from inside
the Keep repository root:

    pytest tests/test_snmp_provider.py -v

The SNMP provider lives at:
    keep/providers/snmp_provider/snmp_provider.py
"""

import unittest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.snmp_provider.snmp_provider import SnmpProvider


# ---------------------------------------------------------------------------
# Shared mock payloads (mirrors alerts_mock.ALERTS["…"]["payload"])
# ---------------------------------------------------------------------------

LINKDOWN_V2C = {
    "version": "v2c",
    "oid": "1.3.6.1.6.3.1.1.5.3",
    "agent_address": "192.168.1.100",
    "community": "public",
    "hostname": "switch01.example.com",
    "description": "Interface GigabitEthernet0/1 is down",
    "varbinds": {
        "1.3.6.1.2.1.1.3.0": "12345678",
        "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.3",
        "1.3.6.1.2.1.2.2.1.1": "1",
        "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
        "1.3.6.1.2.1.2.2.1.7": "2",
        "1.3.6.1.2.1.2.2.1.8": "2",
    },
}

LINKDOWN_V1 = {
    "version": "v1",
    "enterprise": "1.3.6.1.4.1.9.1",
    "agent_address": "10.0.0.1",
    "generic_trap": 2,
    "specific_trap": 0,
    "hostname": "router01",
    "community": "public",
    "varbinds": {
        "1.3.6.1.2.1.2.2.1.1": "3",
        "1.3.6.1.2.1.2.2.1.2": "FastEthernet0/0",
    },
}

LINKUP_V1 = {
    "version": "v1",
    "enterprise": "1.3.6.1.4.1.9.1",
    "agent_address": "10.0.0.1",
    "generic_trap": 3,
    "specific_trap": 0,
    "hostname": "router01",
    "community": "public",
    "varbinds": {
        "1.3.6.1.2.1.2.2.1.1": "3",
        "1.3.6.1.2.1.2.2.1.2": "FastEthernet0/0",
    },
}

COLDSTART_V2C = {
    "version": "v2c",
    "oid": "1.3.6.1.6.3.1.1.5.1",
    "agent_address": "172.16.0.50",
    "community": "monitoring",
    "hostname": "firewall01",
    "varbinds": {
        "1.3.6.1.2.1.1.3.0": "0",
    },
}

AUTHFAILURE_V2C = {
    "version": "v2c",
    "oid": "1.3.6.1.6.3.1.1.5.5",
    "agent_address": "192.168.1.50",
    "community": "public",
    "hostname": "server01",
    "description": "SNMP authentication failure from 10.0.0.99",
}

ENTERPRISE_V3 = {
    "version": "v3",
    "oid": "1.3.6.1.4.1.2636.4.1.1",
    "agent_address": "10.10.10.1",
    "hostname": "juniper-mx01",
    "severity": "critical",
    "description": "Juniper chassis alarm: FPC 0 Major Errors",
    "varbinds": {
        "1.3.6.1.4.1.2636.3.1.15.1.5.9.1.0.0": "FPC 0 Major Errors",
        "1.3.6.1.4.1.2636.3.1.15.1.6.9.1.0.0": "2",
    },
}

CUSTOM_SEVERITY = {
    "version": "v2c",
    "oid": "1.3.6.1.4.1.12345.1.2.3",
    "agent_address": "192.168.100.10",
    "hostname": "app-server-01",
    "severity": "major",
    "description": "Application health check failed",
    "name": "App Health Check Failure",
    "varbinds": {
        "1.3.6.1.4.1.12345.1.2.3.1": "health_check",
        "1.3.6.1.4.1.12345.1.2.3.2": "FAILED",
        "1.3.6.1.4.1.12345.1.2.3.3": "HTTP 503",
    },
}


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestSnmpProviderFormatAlert(unittest.TestCase):
    """Unit tests for SnmpProvider._format_alert()."""

    # ------------------------------------------------------------------
    # 1. SNMPv2c linkDown — the canonical "link is down" alert
    # ------------------------------------------------------------------
    def test_format_alert_v2c_linkdown(self):
        """linkDown v2c trap maps to CRITICAL / FIRING with correct OID and host."""
        alert = SnmpProvider._format_alert(LINKDOWN_V2C)

        self.assertIsInstance(alert, AlertDto)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        self.assertEqual(alert.host, "switch01.example.com")
        self.assertEqual(alert.source, ["snmp"])
        self.assertEqual(alert.oid, "1.3.6.1.6.3.1.1.5.3")

    # ------------------------------------------------------------------
    # 2. SNMPv1 linkDown — generic_trap=2, no "oid" field in payload
    # ------------------------------------------------------------------
    def test_format_alert_v1_linkdown(self):
        """v1 linkDown uses generic_trap integer → oid='2', trap_name='linkDown'."""
        alert = SnmpProvider._format_alert(LINKDOWN_V1)

        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        # OID is derived from the generic_trap integer
        self.assertEqual(alert.oid, "2")
        self.assertEqual(alert.trap_name, "linkDown")

    # ------------------------------------------------------------------
    # 3. SNMPv1 linkUp — recovery event should resolve automatically
    # ------------------------------------------------------------------
    def test_format_alert_v1_linkup_resolves(self):
        """v1 linkUp (generic_trap=3) is a recovery trap → RESOLVED / INFO."""
        alert = SnmpProvider._format_alert(LINKUP_V1)

        self.assertEqual(alert.status, AlertStatus.RESOLVED.value)
        self.assertEqual(alert.severity, AlertSeverity.INFO.value)

    # ------------------------------------------------------------------
    # 4. coldStart — device reboot signal, moderate severity
    # ------------------------------------------------------------------
    def test_format_alert_coldstart(self):
        """coldStart OID maps to WARNING severity and 'coldStart' trap_name."""
        alert = SnmpProvider._format_alert(COLDSTART_V2C)

        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)
        self.assertEqual(alert.trap_name, "coldStart")
        # coldStart is not a resolution event
        self.assertEqual(alert.status, AlertStatus.FIRING.value)

    # ------------------------------------------------------------------
    # 5. authenticationFailure — security event
    # ------------------------------------------------------------------
    def test_format_alert_auth_failure(self):
        """authenticationFailure OID maps to WARNING; description is preserved."""
        alert = SnmpProvider._format_alert(AUTHFAILURE_V2C)

        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)
        self.assertIn("authentication failure", alert.description.lower())

    # ------------------------------------------------------------------
    # 6. Enterprise v3 with user severity="critical" override
    # ------------------------------------------------------------------
    def test_format_alert_custom_severity_critical(self):
        """A user-supplied severity='critical' on an unknown OID → CRITICAL."""
        alert = SnmpProvider._format_alert(ENTERPRISE_V3)

        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)

    # ------------------------------------------------------------------
    # 7. Custom name + severity="major" → HIGH
    # ------------------------------------------------------------------
    def test_format_alert_custom_name_and_major_severity(self):
        """User-supplied name is preserved; 'major' maps to AlertSeverity.HIGH."""
        alert = SnmpProvider._format_alert(CUSTOM_SEVERITY)

        self.assertEqual(alert.name, "App Health Check Failure")
        self.assertEqual(alert.severity, AlertSeverity.HIGH.value)

    # ------------------------------------------------------------------
    # 8. User status override via "status" field in payload
    # ------------------------------------------------------------------
    def test_format_alert_user_status_override_acknowledged(self):
        """A payload with status='acknowledged' overrides the auto-derived status."""
        payload = dict(LINKDOWN_V2C, status="acknowledged")
        alert = SnmpProvider._format_alert(payload)

        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED.value)

    # ------------------------------------------------------------------
    # 9–12. Varbind normalisation variants
    # ------------------------------------------------------------------

    def test_varbinds_dict_passthrough(self):
        """Varbinds provided as a dict are stored unchanged."""
        vb = {"1.3.6.1.2.1.2.2.1.2": "eth0", "1.3.6.1.2.1.2.2.1.8": "2"}
        payload = dict(COLDSTART_V2C, varbinds=vb)
        alert = SnmpProvider._format_alert(payload)

        self.assertIsInstance(alert.varbinds, dict)
        self.assertEqual(alert.varbinds, vb)

    def test_varbinds_list_converted_to_dict(self):
        """Varbinds as a list of {oid, value} objects are merged into a flat dict."""
        vb_list = [
            {"oid": "1.3.6.1.2.1.2.2.1.2", "value": "eth0"},
            {"oid": "1.3.6.1.2.1.2.2.1.8", "value": "2"},
        ]
        payload = dict(COLDSTART_V2C, varbinds=vb_list)
        alert = SnmpProvider._format_alert(payload)

        self.assertIsInstance(alert.varbinds, dict)
        self.assertEqual(alert.varbinds.get("1.3.6.1.2.1.2.2.1.2"), "eth0")
        self.assertEqual(alert.varbinds.get("1.3.6.1.2.1.2.2.1.8"), "2")

    def test_varbinds_string_stored_as_raw(self):
        """Varbinds provided as a raw string are wrapped in {'raw': ...}."""
        raw_text = "IF-MIB::ifIndex.1 = INTEGER: 1\nIF-MIB::ifDescr.1 = STRING: eth0"
        payload = dict(COLDSTART_V2C, varbinds=raw_text)
        alert = SnmpProvider._format_alert(payload)

        self.assertIsInstance(alert.varbinds, dict)
        self.assertIn("raw", alert.varbinds)
        self.assertEqual(alert.varbinds["raw"], raw_text)

    def test_varbinds_missing_defaults_to_empty_dict(self):
        """When the payload contains no varbinds key, varbinds defaults to {}."""
        payload = {k: v for k, v in AUTHFAILURE_V2C.items() if k != "varbinds"}
        alert = SnmpProvider._format_alert(payload)

        self.assertIsInstance(alert.varbinds, dict)
        self.assertEqual(alert.varbinds, {})

    # ------------------------------------------------------------------
    # 13. Empty-dict payload — graceful degradation
    # ------------------------------------------------------------------
    def test_empty_event_does_not_crash(self):
        """An empty dict should produce an AlertDto with safe defaults."""
        alert = SnmpProvider._format_alert({})

        self.assertIsInstance(alert, AlertDto)
        # Severity and status should be valid enum values (stored as strings)
        self.assertIn(alert.severity, [e.value for e in AlertSeverity])
        self.assertIn(alert.status, [e.value for e in AlertStatus])
        # Source must always be tagged
        self.assertEqual(alert.source, ["snmp"])

    # ------------------------------------------------------------------
    # 14. simulate_alert() reads alerts_mock correctly
    # ------------------------------------------------------------------
    def test_simulate_alert_returns_dict(self):
        """SnmpProvider.simulate_alert() must not crash and must return a dict."""
        # simulate_alert() is a classmethod on BaseProvider that imports
        # the sibling alerts_mock module — this validates the mock is wired up.
        result = SnmpProvider.simulate_alert()

        self.assertIsInstance(result, dict)
        # The returned dict should have at least one of the well-known fields
        self.assertTrue(
            any(k in result for k in ("version", "oid", "agent_address", "hostname")),
            f"simulate_alert() returned unexpected dict: {result}",
        )

    # ------------------------------------------------------------------
    # 15. Integer severity field must not crash (the .lower() guard)
    # ------------------------------------------------------------------
    def test_severity_int_does_not_crash(self):
        """A numeric severity value (e.g. from a raw SNMP numeric field) must
        not raise an AttributeError from calling .lower() on an int."""
        payload = dict(COLDSTART_V2C, severity=5)  # integer, not a string
        # This should not raise
        alert = SnmpProvider._format_alert(payload)

        self.assertIsInstance(alert, AlertDto)
        # Integer 5 doesn't match any SEVERITIES_MAP key, so the OID-derived
        # default (WARNING for coldStart) applies.
        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)


if __name__ == "__main__":
    unittest.main()
