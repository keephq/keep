"""
Tests for the SkyWalking provider.
"""

import pytest
from datetime import datetime, timezone

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.skywalking_provider.skywalking_provider import SkywalkingProvider


class TestSkywalkingProvider:
    """Test SkyWalking provider."""

    def test_format_alert_service_scope(self):
        """Test formatting a service-level alert."""
        event = {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "order-service",
            "id0": "c2VydmljZTE=.1",
            "id1": "",
            "ruleName": "service_resp_time_rule",
            "alarmMessage": "Alarm: Service order-service response time is higher than 1000ms in 3 minutes of last 10 minutes.",
            "tags": [
                {"key": "level", "value": "WARNING"}
            ],
            "startTime": 1704067200000
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.id == "SERVICE:order-service:service_resp_time_rule"
        assert alert.name == "service_resp_time_rule"
        assert alert.scope == "SERVICE"
        assert alert.service == "order-service"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING
        assert "order-service" in alert.description
        assert alert.tags == {"level": "WARNING"}

    def test_format_alert_endpoint_scope(self):
        """Test formatting an endpoint-level alert."""
        event = {
            "scopeId": 2,
            "scope": "ENDPOINT",
            "name": "/api/orders",
            "id0": "c2VydmljZTE=.1_L3VzZXI=",
            "id1": "",
            "ruleName": "endpoint_percent_rule",
            "alarmMessage": "Alarm: Successful rate of endpoint /api/orders is lower than 75%",
            "tags": [
                {"key": "level", "value": "CRITICAL"}
            ],
            "startTime": 1704067200000
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.scope == "ENDPOINT"
        assert alert.endpoint == "/api/orders"
        assert alert.service is None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_instance_scope(self):
        """Test formatting a service instance-level alert."""
        event = {
            "scopeId": 3,
            "scope": "SERVICE_INSTANCE",
            "name": "order-service-01",
            "id0": "c2VydmljZTE=.1_MQ==",
            "id1": "",
            "ruleName": "instance_jvm_memory_rule",
            "alarmMessage": "Alarm: Service Instance order-service-01 JVM memory usage is higher than 80%",
            "tags": [
                {"key": "level", "value": "HIGH"}
            ],
            "startTime": 1704067200000
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.scope == "SERVICE_INSTANCE"
        assert alert.instance == "order-service-01"
        assert alert.severity == AlertSeverity.HIGH

    def test_format_alert_no_tags(self):
        """Test formatting an alert without tags."""
        event = {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "test-service",
            "id0": "test-id",
            "id1": "",
            "ruleName": "test_rule",
            "alarmMessage": "Test alarm message",
            "startTime": 1704067200000
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.severity == AlertSeverity.WARNING  # Default severity
        assert alert.tags == {}

    def test_format_alert_no_rule_name(self):
        """Test formatting an alert without a rule name."""
        event = {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "test-service",
            "id0": "test-id",
            "id1": "",
            "alarmMessage": "Test alarm message",
            "tags": [],
            "startTime": 1704067200000
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.id == "SERVICE:test-service"
        assert alert.name == "SkyWalking SERVICE Alert"

    def test_format_alert_invalid_timestamp(self):
        """Test formatting an alert with invalid timestamp."""
        event = {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "test-service",
            "id0": "test-id",
            "alarmMessage": "Test alarm",
            "startTime": "invalid",
            "tags": []
        }

        alert = SkywalkingProvider._format_alert(event)

        # Should still create alert with current time
        assert alert.lastReceived is not None
        assert alert.startedAt is not None

    def test_format_alert_no_timestamp(self):
        """Test formatting an alert without timestamp."""
        event = {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "test-service",
            "id0": "test-id",
            "alarmMessage": "Test alarm",
            "tags": []
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.lastReceived is not None
        assert alert.startedAt is not None

    def test_severity_mapping(self):
        """Test that all severity levels are mapped correctly."""
        test_cases = [
            ("CRITICAL", AlertSeverity.CRITICAL),
            ("HIGH", AlertSeverity.HIGH),
            ("WARNING", AlertSeverity.WARNING),
            ("WARN", AlertSeverity.WARNING),
            ("INFO", AlertSeverity.INFO),
            ("DEBUG", AlertSeverity.INFO),
            ("UNKNOWN", AlertSeverity.WARNING),  # Default
        ]

        for level, expected_severity in test_cases:
            event = {
                "scopeId": 1,
                "scope": "SERVICE",
                "name": "test",
                "alarmMessage": "Test",
                "tags": [{"key": "level", "value": level}],
                "startTime": 1704067200000
            }

            alert = SkywalkingProvider._format_alert(event)
            assert alert.severity == expected_severity, f"Failed for level: {level}"

    def test_format_alert_multiple_tags(self):
        """Test formatting an alert with multiple tags."""
        event = {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "test-service",
            "id0": "test-id",
            "ruleName": "test_rule",
            "alarmMessage": "Test alarm",
            "tags": [
                {"key": "level", "value": "CRITICAL"},
                {"key": "env", "value": "production"},
                {"key": "team", "value": "platform"}
            ],
            "startTime": 1704067200000
        }

        alert = SkywalkingProvider._format_alert(event)

        assert alert.tags == {
            "level": "CRITICAL",
            "env": "production",
            "team": "platform"
        }
        assert alert.severity == AlertSeverity.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__])
