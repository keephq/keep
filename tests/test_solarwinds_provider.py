"""
Tests for the SolarWinds Orion webhook provider.

Covers _format_alert() field mapping, severity resolution, status logic,
timestamp parsing, extra-field pass-through, and simulate_alert().

Run from the solarwinds-provider directory:
    PYTHONPATH=/path/to/keep-repo pytest tests/test_solarwinds_provider.py -v
"""

import copy
import sys
import os
import unittest

# ---------------------------------------------------------------------------
# Path setup
# The provider lives in its own folder tree; the real Keep package lives in
# the cloned repo.  Add both to sys.path so both import trees are reachable.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROVIDER_ROOT = os.path.dirname(_HERE)           # solarwinds-provider/
_REPO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(_PROVIDER_ROOT)),  # research/autonomous-income/
    "repos", "keep",
)

for _p in (_PROVIDER_ROOT, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus  # noqa: E402
from keep.providers.solarwinds_provider.solarwinds_provider import (  # noqa: E402
    SolarwindsProvider,
)
from keep.providers.solarwinds_provider.alerts_mock import ALERTS  # noqa: E402

# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def _fmt(payload: dict) -> AlertDto:
    """Call the static formatter with a copy so tests stay independent."""
    return SolarwindsProvider._format_alert(copy.deepcopy(payload))


def _payload(key: str) -> dict:
    """Return a deep copy of a named mock payload."""
    return copy.deepcopy(ALERTS[key]["payload"])


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestSolarwindsProvider(unittest.TestCase):

    # -----------------------------------------------------------------------
    # 1. Node-down — canonical happy path
    # -----------------------------------------------------------------------

    def test_format_alert_node_down(self):
        """Severity 2 -> CRITICAL, FIRING, correct host / id / source."""
        alert = _fmt(_payload("node_down"))

        self.assertIsInstance(alert, AlertDto)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        self.assertEqual(alert.host, "core-sw-01.example.com")
        self.assertEqual(alert.id, "8819")
        self.assertEqual(alert.source, ["solarwinds"])
        self.assertEqual(alert.name, "Node Down")

    # -----------------------------------------------------------------------
    # 2. High CPU — Severity 1 -> WARNING
    # -----------------------------------------------------------------------

    def test_format_alert_high_cpu(self):
        """Severity 1 -> WARNING, status FIRING."""
        alert = _fmt(_payload("high_cpu"))

        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        self.assertEqual(alert.id, "9203")
        self.assertEqual(alert.name, "High CPU Load")

    # -----------------------------------------------------------------------
    # 3. Informational severity (integer 0)
    # -----------------------------------------------------------------------

    def test_format_alert_info_severity(self):
        """Severity 0 -> INFO."""
        alert = _fmt(_payload("interface_traffic"))

        self.assertEqual(alert.severity, AlertSeverity.INFO.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)

    # -----------------------------------------------------------------------
    # 4. Fatal / Severity 3 -> CRITICAL (Keep has no Fatal tier)
    # -----------------------------------------------------------------------

    def test_format_alert_fatal_severity(self):
        """Severity 3 -> CRITICAL (mapped; no Fatal in Keep)."""
        alert = _fmt(_payload("disk_full_acknowledged"))

        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)

    # -----------------------------------------------------------------------
    # 5. Acknowledged as string "True" -> ACKNOWLEDGED
    # -----------------------------------------------------------------------

    def test_format_alert_string_acknowledged(self):
        """Acknowledged='True' (string) -> status ACKNOWLEDGED."""
        # disk_full_acknowledged uses Acknowledged="True"
        alert = _fmt(_payload("disk_full_acknowledged"))

        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED.value)

    # -----------------------------------------------------------------------
    # 6. Acknowledged as bool True -> ACKNOWLEDGED
    # -----------------------------------------------------------------------

    def test_format_alert_bool_acknowledged(self):
        """Acknowledged=True (bool) -> status ACKNOWLEDGED."""
        # high_memory_resolved uses Acknowledged=True (bool)
        alert = _fmt(_payload("high_memory_resolved"))

        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED.value)

    # -----------------------------------------------------------------------
    # 7. Severity as string integer "1" -> WARNING
    # -----------------------------------------------------------------------

    def test_format_alert_string_severity_as_int(self):
        """Severity='1' (string containing an integer) -> WARNING."""
        alert = _fmt(_payload("interface_down_string_severity"))

        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)

    # -----------------------------------------------------------------------
    # 8. Named string severities: "critical", "error", "fatal"
    # -----------------------------------------------------------------------

    def test_format_alert_named_string_severity(self):
        """Named string severities map correctly."""
        cases = [
            ("critical",     AlertSeverity.CRITICAL.value),
            ("error",        AlertSeverity.HIGH.value),
            ("fatal",        AlertSeverity.CRITICAL.value),
            ("warning",      AlertSeverity.WARNING.value),
            ("information",  AlertSeverity.INFO.value),
            ("info",         AlertSeverity.INFO.value),
        ]
        for raw, expected in cases:
            with self.subTest(severity=raw):
                payload = _payload("node_down")
                payload["Severity"] = raw
                alert = _fmt(payload)
                self.assertEqual(alert.severity, expected)

    # -----------------------------------------------------------------------
    # 9. Timestamp with UTC offset "+00:00"
    # -----------------------------------------------------------------------

    def test_format_alert_timestamp_with_offset(self):
        """TimeOfAlert with +00:00 offset is parsed and stored as ISO string."""
        # node_down uses "2024-06-12T14:32:07+00:00"
        alert = _fmt(_payload("node_down"))

        self.assertIsNotNone(alert.lastReceived)
        self.assertIsInstance(alert.lastReceived, str)
        # AlertDto normalises to UTC; date portion must survive
        self.assertIn("2024-06-12", alert.lastReceived)

    # -----------------------------------------------------------------------
    # 10. Timestamp ending in Z
    # -----------------------------------------------------------------------

    def test_format_alert_timestamp_with_z(self):
        """TimeOfAlert ending in Z is parsed correctly."""
        # disk_full_acknowledged uses "2024-06-12T16:48:00Z"
        alert = _fmt(_payload("disk_full_acknowledged"))

        self.assertIsNotNone(alert.lastReceived)
        self.assertIsInstance(alert.lastReceived, str)
        self.assertIn("2024-06-12", alert.lastReceived)

    # -----------------------------------------------------------------------
    # 11. Invalid timestamp -> pydantic fills in current time (no crash)
    # -----------------------------------------------------------------------

    def test_format_alert_timestamp_invalid(self):
        """TimeOfAlert='not-a-date' must not crash; pydantic provides a fallback."""
        payload = _payload("node_down")
        payload["TimeOfAlert"] = "not-a-date"

        # Provider sets last_received=None on parse failure.  AlertDto.validate_last_received
        # substitutes datetime.now() when the value is falsy, so the DTO is always valid.
        alert = _fmt(payload)

        self.assertIsInstance(alert, AlertDto)
        self.assertIsNotNone(alert.lastReceived)
        self.assertNotEqual(alert.lastReceived, "not-a-date")

    # -----------------------------------------------------------------------
    # 12. AlertStatus="Reset" -> RESOLVED
    # -----------------------------------------------------------------------

    def test_format_alert_reset_status(self):
        """AlertStatus='Reset' overrides Acknowledged and maps to RESOLVED."""
        payload = _payload("node_down")
        payload["AlertStatus"] = "Reset"
        payload["Acknowledged"] = False

        alert = _fmt(payload)

        self.assertEqual(alert.status, AlertStatus.RESOLVED.value)

    # -----------------------------------------------------------------------
    # 13. AlertStatus="Cleared" -> RESOLVED
    # -----------------------------------------------------------------------

    def test_format_alert_cleared_status(self):
        """AlertStatus='Cleared' maps to RESOLVED."""
        payload = _payload("node_down")
        payload["AlertStatus"] = "Cleared"

        alert = _fmt(payload)

        self.assertEqual(alert.status, AlertStatus.RESOLVED.value)

    # -----------------------------------------------------------------------
    # 14. Extra / unknown fields pass through to AlertDto
    # -----------------------------------------------------------------------

    def test_format_alert_extra_fields_passthrough(self):
        """Unknown payload keys should be accessible on the AlertDto via extra."""
        payload = _payload("node_down")
        payload["CustomField"] = "custom_value"
        payload["TeamOwner"] = "network-ops"

        alert = _fmt(payload)

        self.assertEqual(getattr(alert, "CustomField"), "custom_value")
        self.assertEqual(getattr(alert, "TeamOwner"), "network-ops")

    # -----------------------------------------------------------------------
    # 15. IP_Address flows through **extra (not in known_keys)
    # -----------------------------------------------------------------------

    def test_format_alert_ip_address_passthrough(self):
        """IP_Address is intentionally outside known_keys and must reach AlertDto."""
        payload = _payload("node_down")
        # node_down already has IP_Address="10.0.1.1"

        alert = _fmt(payload)

        self.assertEqual(getattr(alert, "IP_Address"), "10.0.1.1")

    # -----------------------------------------------------------------------
    # 16. Empty payload -> no crash, returns AlertDto with safe defaults
    # -----------------------------------------------------------------------

    def test_format_alert_empty_event(self):
        """An entirely empty dict should not raise; defaults should be applied."""
        alert = _fmt({})

        self.assertIsInstance(alert, AlertDto)
        self.assertEqual(alert.name, "SolarWinds Alert")
        self.assertEqual(alert.severity, AlertSeverity.INFO.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        self.assertEqual(alert.source, ["solarwinds"])

    # -----------------------------------------------------------------------
    # 17. Only AlertName present -> no crash
    # -----------------------------------------------------------------------

    def test_format_alert_missing_optional_fields(self):
        """Payload with only AlertName present should not raise."""
        alert = _fmt({"AlertName": "Minimal Alert"})

        self.assertIsInstance(alert, AlertDto)
        self.assertEqual(alert.name, "Minimal Alert")
        self.assertEqual(alert.severity, AlertSeverity.INFO.value)
        self.assertEqual(alert.status, AlertStatus.FIRING.value)
        self.assertEqual(alert.source, ["solarwinds"])

    # -----------------------------------------------------------------------
    # 18. simulate_alert() — smoke test
    # -----------------------------------------------------------------------

    def test_simulate_alert(self):
        """simulate_alert() should return a dict without raising."""
        result = SolarwindsProvider.simulate_alert()

        self.assertIsInstance(result, dict)
        self.assertIn("AlertName", result)

    # -----------------------------------------------------------------------
    # Bonus: NodeCaption fallback when NodeName is absent
    # -----------------------------------------------------------------------

    def test_format_alert_node_caption_fallback(self):
        """When NodeName is absent, NodeCaption is used as host."""
        payload = _payload("node_down")
        del payload["NodeName"]

        alert = _fmt(payload)

        self.assertEqual(alert.host, "Core Switch 01")

    # -----------------------------------------------------------------------
    # Bonus: AlertObjectID used as id fallback when AlertActiveID is absent
    # -----------------------------------------------------------------------

    def test_format_alert_id_fallback_to_object_id(self):
        """When AlertActiveID is absent, AlertObjectID is used as id."""
        payload = _payload("node_down")
        del payload["AlertActiveID"]

        alert = _fmt(payload)

        self.assertEqual(alert.id, "42")

    # -----------------------------------------------------------------------
    # Bonus: Case-insensitive named severity lookup
    # -----------------------------------------------------------------------

    def test_format_alert_named_severity_case_insensitive(self):
        """SEVERITIES_MAP_STR lookup is case-insensitive."""
        cases = [
            ("CRITICAL", AlertSeverity.CRITICAL.value),
            ("Warning",  AlertSeverity.WARNING.value),
            ("INFO",     AlertSeverity.INFO.value),
            ("Fatal",    AlertSeverity.CRITICAL.value),
            ("ERROR",    AlertSeverity.HIGH.value),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                payload = _payload("node_down")
                payload["Severity"] = raw
                alert = _fmt(payload)
                self.assertEqual(alert.severity, expected)

    # -----------------------------------------------------------------------
    # Bonus: Unknown severity string defaults to INFO (not a crash)
    # -----------------------------------------------------------------------

    def test_format_alert_unknown_severity_string_defaults_to_info(self):
        """An unrecognised severity string should fall back to INFO."""
        payload = _payload("node_down")
        payload["Severity"] = "supercritical"

        alert = _fmt(payload)

        self.assertEqual(alert.severity, AlertSeverity.INFO.value)

    # -----------------------------------------------------------------------
    # Bonus: description prefers AlertDescription over AlertMessage
    # -----------------------------------------------------------------------

    def test_format_alert_description_prefers_alert_description(self):
        """AlertDescription takes precedence over AlertMessage."""
        payload = {
            "AlertName": "Test",
            "AlertDescription": "Detailed description",
            "AlertMessage": "Short message",
        }
        alert = _fmt(payload)

        self.assertEqual(alert.description, "Detailed description")

    def test_format_alert_description_falls_back_to_message(self):
        """When AlertDescription is absent, AlertMessage is used as description."""
        payload = {
            "AlertName": "Test",
            "AlertMessage": "Short message",
        }
        alert = _fmt(payload)

        self.assertEqual(alert.description, "Short message")

    # -----------------------------------------------------------------------
    # Bonus: AlertStatus="Resolved" -> RESOLVED
    # -----------------------------------------------------------------------

    def test_format_alert_resolved_status_string(self):
        """AlertStatus='Resolved' maps to RESOLVED."""
        payload = _payload("node_down")
        payload["AlertStatus"] = "Resolved"

        alert = _fmt(payload)

        self.assertEqual(alert.status, AlertStatus.RESOLVED.value)

    # -----------------------------------------------------------------------
    # Bonus: AlertStatus takes precedence over Acknowledged
    # -----------------------------------------------------------------------

    def test_format_alert_alert_status_beats_acknowledged(self):
        """AlertStatus='Reset' resolves even when Acknowledged=True."""
        payload = _payload("node_down")
        payload["AlertStatus"] = "Reset"
        payload["Acknowledged"] = True

        alert = _fmt(payload)

        self.assertEqual(alert.status, AlertStatus.RESOLVED.value)

    # -----------------------------------------------------------------------
    # Bonus: FINGERPRINT_FIELDS declaration
    # -----------------------------------------------------------------------

    def test_fingerprint_fields_declared(self):
        """FINGERPRINT_FIELDS must include AlertActiveID."""
        self.assertIn("AlertActiveID", SolarwindsProvider.FINGERPRINT_FIELDS)

    # -----------------------------------------------------------------------
    # Bonus: Provider display metadata
    # -----------------------------------------------------------------------

    def test_provider_display_name(self):
        """PROVIDER_DISPLAY_NAME must be 'SolarWinds'."""
        self.assertEqual(SolarwindsProvider.PROVIDER_DISPLAY_NAME, "SolarWinds")

    def test_provider_tags(self):
        """PROVIDER_TAGS must include 'alert'."""
        self.assertIn("alert", SolarwindsProvider.PROVIDER_TAGS)

    def test_provider_category(self):
        """PROVIDER_CATEGORY must include Monitoring and Infrastructure."""
        self.assertIn("Monitoring", SolarwindsProvider.PROVIDER_CATEGORY)
        self.assertIn("Infrastructure", SolarwindsProvider.PROVIDER_CATEGORY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
