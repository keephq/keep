import pytest

from keep.providers.prtg_provider.prtg_provider import PrtgProvider


# Sample full PRTG webhook event
FULL_EVENT = {
    "host": "192.168.1.100",
    "name": "Ping Sensor",
    "sensor": "Ping",
    "message": "Sensor is down",
    "status": "Down",
    "lastvalue": "0 ms",
    "device": "Server-01",
    "group": "Production",
    "probe": "Probe1",
    "link": "https://prtg.example.com/sensor.htm?id=1234",
    "id": "1234",
    "sensorid": "1234",
    "datetime": "2026-05-22 10:30:00",
    "down": "5 minutes",
    "sensor_type": "Ping",
    "tags": "production,critical",
    "priority": "5",
}


class TestPrtgFormatAlert:
    """Tests for PrtgProvider._format_alert."""

    def test_format_alert_full_event(self):
        alert = PrtgProvider._format_alert(FULL_EVENT)
        assert alert.id == "1234"
        assert alert.name == "Server-01 - Ping"
        assert alert.message == "Sensor is down"
        assert alert.severity.value == "critical"
        assert alert.status.value == "firing"
        assert str(alert.url) == "https://prtg.example.com/sensor.htm?id=1234"
        assert alert.lastReceived == "2026-05-22 10:30:00"
        assert alert.source == ["prtg"]
        assert alert.sensor == "Ping"
        assert alert.device == "Server-01"
        assert alert.group == "Production"
        assert alert.probe == "Probe1"
        assert alert.lastvalue == "0 ms"
        assert alert.down == "5 minutes"
        assert alert.sensor_type == "Ping"
        assert alert.tags == "production,critical"
        assert alert.priority == "5"

    def test_format_alert_minimal_event(self):
        """Only required fields — everything else should have safe defaults."""
        event = {"sensor": "CPU Load", "device": "Router-01", "status": "Down"}
        alert = PrtgProvider._format_alert(event)
        assert alert.name == "Router-01 - CPU Load"
        assert alert.severity.value == "critical"
        assert alert.status.value == "firing"
        assert alert.url is None
        assert alert.id == ""

    def test_format_alert_status_mapping(self):
        """All PRTG statuses map correctly."""
        cases = {
            "Up": ("resolved", "info"),
            "Down": ("firing", "critical"),
            "Warning": ("firing", "warning"),
            "Paused": ("suppressed", "info"),
            "Unknown": ("firing", "info"),
        }
        for status, (expected_status, expected_severity) in cases.items():
            event = dict(FULL_EVENT, status=status, priority="")
            alert = PrtgProvider._format_alert(event)
            assert alert.status.value == expected_status, f"status={status}"
            assert alert.severity.value == expected_severity, f"status={status}"

    def test_format_alert_severity_from_priority(self):
        """Priority 1-5 maps to correct severity levels."""
        cases = {
            "1": "info",
            "2": "warning",
            "3": "warning",
            "4": "high",
            "5": "critical",
        }
        for priority, expected in cases.items():
            event = dict(FULL_EVENT, priority=priority, status="Unknown")
            alert = PrtgProvider._format_alert(event)
            assert alert.severity.value == expected, f"priority={priority}"

    def test_format_alert_severity_fallback_to_status(self):
        """When priority is missing/empty, severity falls back to status mapping."""
        event = dict(FULL_EVENT, priority="", status="Down")
        alert = PrtgProvider._format_alert(event)
        assert alert.severity.value == "critical"

        event2 = dict(FULL_EVENT, priority=None, status="Warning")
        alert2 = PrtgProvider._format_alert(event2)
        assert alert2.severity.value == "warning"

    def test_format_alert_unresolved_placeholders(self):
        """PRTG may send %%placeholder when values aren't configured.
        These must be sanitized — especially %%link which would cause
        ValidationError on AlertDto.url (AnyHttpUrl type)."""
        event = dict(FULL_EVENT, link="%%link", sensor_type="%%sensor_type")
        alert = PrtgProvider._format_alert(event)
        assert alert.url is None  # %%link sanitized to None
        # Other %% fields are just stored as strings (Extra.allow)
        assert alert.sensor_type == "%%sensor_type"

    def test_format_alert_sensorid_precedence(self):
        """sensorid takes precedence over id when both present."""
        event = dict(FULL_EVENT, sensorid="999", id="1234")
        alert = PrtgProvider._format_alert(event)
        assert alert.id == "999"

    def test_format_alert_sensorid_zero(self):
        """sensorid='0' should not fall through to id (0 is falsy but valid)."""
        event = dict(FULL_EVENT, sensorid="0", id="1234")
        alert = PrtgProvider._format_alert(event)
        assert alert.id == "0"

    def test_format_alert_empty_event(self):
        """Empty dict should not crash — safe defaults for everything."""
        alert = PrtgProvider._format_alert({})
        assert alert.name == "Unknown Device - Unknown Sensor"
        assert alert.status.value == "firing"
        assert alert.severity.value == "info"
        assert alert.url is None
        assert alert.id == ""

    def test_format_alert_numeric_priority(self):
        """PRTG might send priority as integer instead of string."""
        event = dict(FULL_EVENT, priority=5)
        alert = PrtgProvider._format_alert(event)
        assert alert.severity.value == "critical"

    def test_format_alert_host_as_device_fallback(self):
        """When device is missing, host is used as device name."""
        event = {"host": "10.0.0.1", "sensor": "Ping", "status": "Up"}
        alert = PrtgProvider._format_alert(event)
        assert "10.0.0.1" in alert.name
        assert alert.device == "10.0.0.1"
