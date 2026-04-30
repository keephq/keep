"""
Tests for Coroot provider.
"""

import pytest
from datetime import datetime, timezone
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.coroot_provider.coroot_provider import CorootProvider


class TestCorootProvider:
    """Test cases for CorootProvider."""

    def test_format_alerts_empty_list(self):
        """Test formatting empty alert list."""
        result = CorootProvider._format_alerts([])
        assert result == []

    def test_format_alerts_empty_dict(self):
        """Test formatting empty alert dict."""
        result = CorootProvider._format_alerts({"alerts": []})
        assert result == []

    def test_format_alerts_simple_alert(self):
        """Test formatting a simple alert."""
        alerts_data = {
            "alerts": [
                {
                    "id": "test-alert-1",
                    "name": "High CPU Usage",
                    "description": "CPU usage is above 90%",
                    "severity": "warning",
                    "status": "firing",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "labels": {
                        "service": "api-gateway",
                        "severity": "warning"
                    }
                }
            ]
        }

        result = CorootProvider._format_alerts(alerts_data)

        assert len(result) == 1
        alert = result[0]
        assert isinstance(alert, AlertDto)
        assert alert.name == "High CPU Usage"
        assert alert.description == "CPU usage is above 90%"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
        assert alert.service == "api-gateway"
        assert alert.source == ["coroot"]

    def test_format_alerts_critical(self):
        """Test formatting critical severity alert."""
        alerts_data = [
            {
                "id": "critical-1",
                "name": "Database Connection Failed",
                "severity": "critical",
                "status": "firing",
            }
        ]

        result = CorootProvider._format_alerts(alerts_data)

        assert len(result) == 1
        assert result[0].severity == AlertSeverity.CRITICAL
        assert result[0].status == AlertStatus.FIRING

    def test_format_alerts_resolved(self):
        """Test formatting resolved alert."""
        alerts_data = [
            {
                "id": "resolved-1",
                "name": "Memory Alert",
                "severity": "info",
                "status": "resolved",
            }
        ]

        result = CorootProvider._format_alerts(alerts_data)

        assert len(result) == 1
        assert result[0].status == AlertStatus.RESOLVED

    def test_format_alerts_list_response(self):
        """Test formatting alerts from list response."""
        alerts_data = [
            {
                "alert_id": "alert-1",
                "name": "Alert One",
                "summary": "Summary of alert one",
                "severity": "high",
                "state": "open",
                "application": "app-1",
                "created_at": "2024-01-15T12:00:00Z",
            },
            {
                "alert_id": "alert-2",
                "name": "Alert Two",
                "description": "Description of alert two",
                "severity": "low",
                "status": "closed",
                "service": "service-2",
            }
        ]

        result = CorootProvider._format_alerts(alerts_data)

        assert len(result) == 2
        assert result[0].name == "Alert One"
        assert result[0].severity == AlertSeverity.HIGH
        assert result[0].service == "app-1"
        assert result[1].name == "Alert Two"
        assert result[1].severity == AlertSeverity.LOW
        assert result[1].status == AlertStatus.RESOLVED

    def test_severity_mapping(self):
        """Test all severity mappings."""
        test_cases = [
            ("critical", AlertSeverity.CRITICAL),
            ("error", AlertSeverity.HIGH),
            ("high", AlertSeverity.HIGH),
            ("warning", AlertSeverity.WARNING),
            ("warn", AlertSeverity.WARNING),
            ("medium", AlertSeverity.WARNING),
            ("info", AlertSeverity.INFO),
            ("low", AlertSeverity.LOW),
            ("unknown", AlertSeverity.INFO),  # default
        ]

        for input_severity, expected in test_cases:
            alerts_data = [{"id": "test", "name": "Test", "severity": input_severity}]
            result = CorootProvider._format_alerts(alerts_data)
            assert result[0].severity == expected, f"Failed for severity: {input_severity}"

    def test_status_mapping(self):
        """Test all status mappings."""
        test_cases = [
            ("firing", AlertStatus.FIRING),
            ("open", AlertStatus.FIRING),
            ("resolved", AlertStatus.RESOLVED),
            ("closed", AlertStatus.RESOLVED),
        ]

        for input_status, expected in test_cases:
            alerts_data = [{"id": "test", "name": "Test", "status": input_status}]
            result = CorootProvider._format_alerts(alerts_data)
            assert result[0].status == expected, f"Failed for status: {input_status}"
