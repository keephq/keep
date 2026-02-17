"""Tests for Kapacitor provider."""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.kapacitor_provider.kapacitor_provider import (
    KapacitorProvider,
)


class TestKapacitorFormatAlert:
    """Test _format_alert with different Kapacitor alert levels."""

    @staticmethod
    def _make_event(level, alert_id="test_alert:host=srv1", message="Test alert", details="Details"):
        return {
            "id": alert_id,
            "message": message,
            "details": details,
            "level": level,
            "time": "2024-01-15T10:30:00Z",
            "duration": "5m0s",
            "previousLevel": "OK",
            "data": {"series": []},
        }

    def test_critical_level(self):
        event = self._make_event("CRITICAL", message="CPU critically high")
        alert = KapacitorProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert alert.name == "CPU critically high"
        assert "kapacitor" in alert.source

    def test_warning_level(self):
        event = self._make_event("WARNING", message="Disk usage warning")
        alert = KapacitorProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_info_level(self):
        event = self._make_event("INFO", message="Info notification")
        alert = KapacitorProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING

    def test_ok_level_resolved(self):
        event = self._make_event("OK", message="Service recovered")
        alert = KapacitorProvider._format_alert(event)
        assert alert.severity == AlertSeverity.LOW
        assert alert.status == AlertStatus.RESOLVED

    def test_unknown_level_defaults_to_info(self):
        event = self._make_event("UNKNOWN_LEVEL")
        alert = KapacitorProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING

    def test_alert_fields_populated(self):
        event = self._make_event(
            "CRITICAL",
            alert_id="cpu_alert:host=web01",
            message="CPU high",
            details="CPU at 99%",
        )
        alert = KapacitorProvider._format_alert(event)
        assert alert.id == "cpu_alert:host=web01"
        assert alert.description == "CPU at 99%"
        assert alert.duration == "5m0s"
        assert alert.lastReceived is not None
