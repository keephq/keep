"""
Tests for the Flowtriq DDoS detection provider.

Tests cover:
- Alert formatting from webhook payloads (nested incident/node structure)
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
        """Complete DDoS incident alert with all fields."""
        event = {
            "source": "flowtriq",
            "event_type": "incident.detected",
            "timestamp": "2026-06-25T10:00:00Z",
            "incident": {
                "id": "atk-12345",
                "title": "UDP Flood on 203.0.113.50",
                "severity": "critical",
                "status": "active",
                "attack_family": "udp_flood",
                "peak_bps": 5_000_000_000,
                "peak_pps": 2_500_000,
                "source_ip_count": 300,
                "duration_seconds": 45,
                "started_at": "2026-06-25T10:00:00Z",
                "resolved_at": None,
                "dashboard_url": "https://flowtriq.com/incident/atk-12345",
                "description": "Volumetric UDP flood detected",
            },
            "node": {
                "name": "web-01",
                "ip_address": "203.0.113.50",
            },
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
        assert alert.labels["attack_family"] == "udp_flood"
        assert alert.labels["node_ip_address"] == "203.0.113.50"
        assert alert.labels["node_name"] == "web-01"
        assert alert.labels["source_ip_count"] == "300"
        assert alert.url == "https://flowtriq.com/incident/atk-12345"

    def test_resolved_attack(self):
        """Incident that has ended maps to RESOLVED status."""
        event = {
            "source": "flowtriq",
            "event_type": "incident.resolved",
            "incident": {
                "id": "atk-99999",
                "severity": "high",
                "status": "ended",
                "attack_family": "syn_flood",
                "started_at": "2026-06-25T08:00:00Z",
                "resolved_at": "2026-06-25T08:15:00Z",
            },
            "node": {
                "name": "db-01",
                "ip_address": "10.0.0.1",
            },
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.HIGH
        assert alert.lastReceived == "2026-06-25T08:15:00Z"

    def test_mitigated_status(self):
        """Mitigated status maps to RESOLVED."""
        event = {
            "incident": {
                "id": "atk-555",
                "severity": "warning",
                "status": "mitigated",
            },
            "node": {
                "ip_address": "192.168.1.1",
            },
        }

        alert = FlowtriqProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_minimal_event(self):
        """Minimal webhook payload with only required fields."""
        event = {
            "incident": {
                "id": "atk-minimal",
            },
            "node": {
                "ip_address": "10.0.0.1",
            },
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.id == "atk-minimal"
        assert alert.name == "DDoS Attack on 10.0.0.1"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING
        assert alert.source == ["flowtriq"]

    def test_missing_node(self):
        """Event without node object uses 'unknown' fallback for IP."""
        event = {
            "incident": {"id": "atk-no-node"},
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.name == "DDoS Attack on unknown"
        assert alert.fingerprint == "flowtriq-atk-no-node-unknown"

    def test_missing_id(self):
        """Event without id still produces a valid alert."""
        event = {
            "incident": {
                "severity": "low",
            },
            "node": {
                "ip_address": "10.0.0.1",
            },
        }

        alert = FlowtriqProvider._format_alert(event)

        assert alert.id is None
        assert alert.fingerprint is None
        assert alert.severity == AlertSeverity.LOW

    def test_title_used_as_name(self):
        """When incident has a title field, it is used as the alert name."""
        event = {
            "incident": {
                "id": "atk-title",
                "title": "Custom Attack Title",
                "attack_family": "dns_amplification",
            },
            "node": {
                "ip_address": "10.0.0.1",
            },
        }

        alert = FlowtriqProvider._format_alert(event)
        assert alert.name == "Custom Attack Title"

    def test_empty_event(self):
        """Completely empty event still produces a valid alert."""
        event = {}

        alert = FlowtriqProvider._format_alert(event)

        assert alert.id is None
        assert alert.name == "DDoS Attack on unknown"
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING


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
        event = {
            "incident": {
                "id": "test",
                "severity": flowtriq_severity,
            },
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert alert.severity == expected

    def test_unknown_severity_defaults_to_info(self):
        event = {
            "incident": {
                "id": "test",
                "severity": "unknown_level",
            },
            "node": {"ip_address": "10.0.0.1"},
        }
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
        event = {
            "incident": {
                "id": "test",
                "status": flowtriq_status,
            },
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert alert.status == expected

    def test_unknown_status_defaults_to_firing(self):
        event = {
            "incident": {
                "id": "test",
                "status": "something_else",
            },
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING


class TestBandwidthFormatting:
    """Test bandwidth and packet rate formatting in descriptions."""

    def test_gbps_formatting(self):
        event = {
            "incident": {"id": "t", "peak_bps": 10_000_000_000},
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert "10.0 Gbps" in alert.description

    def test_mbps_formatting(self):
        event = {
            "incident": {"id": "t", "peak_bps": 500_000_000},
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert "500.0 Mbps" in alert.description

    def test_kbps_formatting(self):
        event = {
            "incident": {"id": "t", "peak_bps": 500_000},
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert "500.0 Kbps" in alert.description

    def test_mpps_formatting(self):
        event = {
            "incident": {"id": "t", "peak_pps": 5_000_000},
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert "5.0 Mpps" in alert.description

    def test_kpps_formatting(self):
        event = {
            "incident": {"id": "t", "peak_pps": 500_000},
            "node": {"ip_address": "10.0.0.1"},
        }
        alert = FlowtriqProvider._format_alert(event)
        assert "500.0 Kpps" in alert.description
