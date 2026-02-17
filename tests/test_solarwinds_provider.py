"""Tests for SolarWinds Provider."""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.solarwinds_provider.solarwinds_provider import (
    SolarwindsProvider,
)


class TestSolarwindsFormatAlert(unittest.TestCase):
    """Test _format_alert with various webhook payloads."""

    def test_critical_firing_alert(self):
        event = {
            "AlertActiveID": "1001",
            "AlertName": "Node Down",
            "AlertDescription": "Node is unreachable",
            "AlertMessage": "web-server-01 is down",
            "Severity": 2,
            "Acknowledged": False,
            "TriggeredDateTime": "2024-01-15T10:30:00Z",
            "NodeName": "web-server-01",
            "EntityType": "Orion.Nodes",
            "ObjectType": "Node",
            "status": "firing",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.id, "1001")
        self.assertEqual(alert.name, "Node Down")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.service, "web-server-01")
        self.assertTrue(alert.pushed)
        self.assertEqual(alert.source, ["solarwinds"])

    def test_warning_alert(self):
        event = {
            "AlertActiveID": "2001",
            "AlertName": "High CPU",
            "Severity": 1,
            "status": "firing",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_resolved_alert(self):
        event = {
            "AlertActiveID": "1001",
            "AlertName": "Node Down",
            "Severity": 2,
            "status": "resolved",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_acknowledged_alert(self):
        event = {
            "AlertActiveID": "1001",
            "AlertName": "Node Down",
            "Acknowledged": True,
            "status": "acknowledged",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)

    def test_acknowledged_via_flag(self):
        """When status is not set but Acknowledged is True."""
        event = {
            "AlertActiveID": "1001",
            "AlertName": "Node Down",
            "Acknowledged": True,
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)

    def test_acknowledged_string_true(self):
        """SolarWinds webhook templates may send booleans as strings."""
        event = {
            "AlertActiveID": "1001",
            "AlertName": "Test",
            "Acknowledged": "true",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)

    def test_severity_string_mapping(self):
        for sev_str, expected in [
            ("informational", AlertSeverity.INFO),
            ("warning", AlertSeverity.WARNING),
            ("critical", AlertSeverity.CRITICAL),
            ("notice", AlertSeverity.LOW),
        ]:
            event = {"AlertName": "Test", "Severity": sev_str}
            alert = SolarwindsProvider._format_alert(event)
            self.assertEqual(alert.severity, expected, f"Failed for {sev_str}")

    def test_severity_numeric_string(self):
        event = {"AlertName": "Test", "Severity": "2"}
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_fallback_field_names(self):
        """Test that generic field names work as fallback."""
        event = {
            "id": "9999",
            "name": "Generic Alert",
            "description": "Something happened",
            "message": "Alert message",
            "severity": "warning",
            "status": "firing",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.id, "9999")
        self.assertEqual(alert.name, "Generic Alert")
        self.assertEqual(alert.severity, AlertSeverity.WARNING)

    def test_datetime_parsing(self):
        event = {
            "AlertName": "Test",
            "TriggeredDateTime": "2024-06-15T08:00:00Z",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertIn("2024-06-15", alert.lastReceived)

    def test_datetime_fallback_on_invalid(self):
        event = {
            "AlertName": "Test",
            "TriggeredDateTime": "not-a-date",
        }
        alert = SolarwindsProvider._format_alert(event)
        # Should fall back to current time without raising
        self.assertIsNotNone(alert.lastReceived)

    def test_missing_fields_defaults(self):
        """Minimal payload should still produce a valid AlertDto."""
        event = {}
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.name, "SolarWinds Alert")
        self.assertEqual(alert.status, AlertStatus.FIRING)
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_url_passthrough(self):
        event = {
            "AlertName": "Test",
            "url": "https://solarwinds.example.com/Orion/Alert/1001",
        }
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(
            alert.url, "https://solarwinds.example.com/Orion/Alert/1001"
        )

    def test_environment_field(self):
        event = {"AlertName": "Test", "environment": "production"}
        alert = SolarwindsProvider._format_alert(event)
        self.assertEqual(alert.environment, "production")


class TestSolarwindsProviderParseDateTime(unittest.TestCase):
    def test_iso_with_z(self):
        result = SolarwindsProvider._parse_datetime("2024-01-15T10:30:00Z")
        self.assertIn("2024-01-15", result)

    def test_iso_with_offset(self):
        result = SolarwindsProvider._parse_datetime("2024-01-15T10:30:00+02:00")
        self.assertIn("2024-01-15", result)

    def test_none_returns_current(self):
        result = SolarwindsProvider._parse_datetime(None)
        today = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        self.assertIn(today, result)

    def test_invalid_returns_current(self):
        result = SolarwindsProvider._parse_datetime("garbage")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
