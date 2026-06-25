"""
Tests for the Flowtriq DDoS detection provider.

Tests cover:
- Alert formatting from webhook payloads
- Severity and status mapping
- Handling of missing/partial fields
- Bandwidth and packet rate formatting in descriptions
"""

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.flowtriq_provider.flowtriq_provider import FlowtriqProvider


class TestFormatAlert:
    """Test _format_alert static method with various webhook payloads."""

    def test_full_attack_alert(self):
        """Complete DDoS attack alert with all fields."""
        event = {
            "id": "atk-12345",
            "target_ip": "203.0.113.50",
            "attack_type": "UDP Flood",
            "severity": "critical",
            "status": "active",
            "bandwidth_bps": 5_000_000_000,
            "packets_pps": 2_500_000,
            "started_at": "2026-06-25T10:00:00Z",
            "description": "Volumetric UDP flood detected",
            "source_countries": ["CN", "RU", "BR"],
            "target_port": 53,
            "protocol": "UDP",
            "url": "https://app.flowtriq.com/attacks/atk-12345",
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.id == "atk-12345"
        assert alert.name == "UDP Flood on 203.0.113.50"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert "5.0 Gbps" in alert.description
        assert "2.5 Mpps" in alert.description
        assert alert.fingerprint == "flowtriq-atk-12345-203.0.113.50"
        assert alert.source == ["flowtriq"]
        assert alert.labels["attack_type"] == "UDP Flood"
        assert alert.labels["target_ip"] == "203.0.113.50"
        assert "CN" in alert.labels["source_countries"]
        assert alert.labels["target_port"] == "53"
        assert alert.labels["protocol"] == "UDP"

    def test_resolved_attack(self):
        """Attack that has ended maps to RESOLVED status."""
        event = {
            "id": "atk-99999",
            "target_ip": "10.0.0.1",
            "attack_type": "SYN Flood",
            "severity": "high",
            "status": "ended",
            "started_at": "2026-06-25T08:00:00Z",
            "ended_at": "2026-06-25T08:15:00Z",
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.HIGH
        assert alert.lastReceived == "2026-06-25T08:15:00Z"

    def test_mitigated_status(self):
        """Mitigated status maps to RESOLVED."""
        event = {
            "id": "atk-555",
            "target_ip": "192.168.1.1",
            "severity": "warning",
            "status": "mitigated",
        }

        alert = FlowtriqProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_minimal_event(self):
        """Minimal webhook payload with only required fields."""
        event = {
            "id": "atk-minimal",
            "target_ip": "10.0.0.1",
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.id == "atk-minimal"
        assert alert.name == "DDoS Attack on 10.0.0.1"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING
        assert alert.source == ["flowtriq"]

    def test_missing_target_ip(self):
        """Event without target_ip uses 'unknown' fallback."""
        event = {"id": "atk-no-ip"}

        alert = FlowtriqProvider._format_alert(event)

        assert alert.name == "DDoS Attack on unknown"
        assert alert.fingerprint == "flowtriq-atk-no-ip-unknown"

    def test_missing_id(self):
        """Event without id still produces a valid alert."""
        event = {
            "target_ip": "10.0.0.1",
            "severity": "low",
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.id is None
        assert alert.fingerprint is None
        assert alert.severity == AlertSeverity.LOW


class TestSeverityMapping:
    """Test all severity level mappings."""

    @pytest.mark.parametrize(
        "flowtriq_severity,expected",
        [
            ("critical", AlertSeverity.CRITICAL),
            ("high", AlertSeverity.HIGH),
            ("warning", AlertSeverity.WARNING),
            ("medium", AlertSeverity.WARNING),
            ("low", AlertSeverity.LOW),
            ("info", AlertSeverity.INFO),
            ("CRITICAL", AlertSeverity.CRITICAL),
            ("High", AlertSeverity.HIGH),
        ],
    )
    def test_severity_mapping(self, flowtriq_severity, expected):
        event = {"id": "test", "target_ip": "10.0.0.1", "severity": flowtriq_severity}
        alert = FlowtriqProvider._format_alert(event)
        assert alert.severity == expected

    def test_unknown_severity_defaults_to_info(self):
        event = {"id": "test", "target_ip": "10.0.0.1", "severity": "unknown_level"}
        alert = FlowtriqProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO


class TestStatusMapping:
    """Test all status mappings."""

    @pytest.mark.parametrize(
        "flowtriq_status,expected",
        [
            ("active", AlertStatus.FIRING),
            ("ongoing", AlertStatus.FIRING),
            ("mitigated", AlertStatus.RESOLVED),
            ("ended", AlertStatus.RESOLVED),
            ("resolved", AlertStatus.RESOLVED),
        ],
    )
    def test_status_mapping(self, flowtriq_status, expected):
        event = {"id": "test", "target_ip": "10.0.0.1", "status": flowtriq_status}
        alert = FlowtriqProvider._format_alert(event)
        assert alert.status == expected

    def test_unknown_status_defaults_to_firing(self):
        event = {"id": "test", "target_ip": "10.0.0.1", "status": "something_else"}
        alert = FlowtriqProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING


class TestBandwidthFormatting:
    """Test bandwidth and packet rate formatting in descriptions."""

    def test_gbps_formatting(self):
        event = {"id": "t", "target_ip": "10.0.0.1", "bandwidth_bps": 10_000_000_000}
        alert = FlowtriqProvider._format_alert(event)
        assert "10.0 Gbps" in alert.description

    def test_mbps_formatting(self):
        event = {"id": "t", "target_ip": "10.0.0.1", "bandwidth_bps": 500_000_000}
        alert = FlowtriqProvider._format_alert(event)
        assert "500.0 Mbps" in alert.description

    def test_kbps_formatting(self):
        event = {"id": "t", "target_ip": "10.0.0.1", "bandwidth_bps": 500_000}
        alert = FlowtriqProvider._format_alert(event)
        assert "500.0 Kbps" in alert.description

    def test_mpps_formatting(self):
        event = {"id": "t", "target_ip": "10.0.0.1", "packets_pps": 5_000_000}
        alert = FlowtriqProvider._format_alert(event)
        assert "5.0 Mpps" in alert.description

    def test_kpps_formatting(self):
        event = {"id": "t", "target_ip": "10.0.0.1", "packets_pps": 500_000}
        alert = FlowtriqProvider._format_alert(event)
        assert "500.0 Kpps" in alert.description
