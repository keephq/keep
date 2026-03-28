"""
Unit tests for the Sematext Cloud provider.

Tests cover:
  - Config validation (no-op auth)
  - _format_alert: status derivation (backToNormal, ruleType)
  - _format_alert: severity derivation (priority string + numeric)
  - _format_alert: recovery caps severity to INFO
  - _format_alert: metric context in description
  - _format_alert: label/tag merging
  - _format_alert: ID generation
  - _format_alert: missing/optional fields handled gracefully
  - SEVERITY_MAP completeness
  - RULE_TYPE_STATUS_MAP completeness
"""

import pytest
from unittest.mock import MagicMock

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.sematext_provider.sematext_provider import (
    SematextProvider,
    SematextProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider() -> SematextProvider:
    """Build a SematextProvider (no auth fields needed)."""
    config = ProviderConfig(authentication={})
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return SematextProvider(ctx, "sematext-test", config)


def _critical_alert_event() -> dict:
    """Sematext webhook payload for a CRITICAL alert."""
    return {
        "title": "High CPU Usage",
        "description": "CPU usage exceeded threshold on prod-server-01",
        "ruleType": "ALERT",
        "priority": "CRITICAL",
        "backToNormal": False,
        "threshold": 90.0,
        "metricValue": 97.5,
        "startedAt": "2026-03-29T10:00:00Z",
        "endedAt": None,
        "appName": "Production Monitoring",
        "appType": "Monitoring",
        "alertRuleId": 12345,
        "tags": {"env": "production", "host": "prod-server-01"},
        "url": "https://apps.sematext.com/ui/alerts/12345",
    }


def _warning_alert_event() -> dict:
    return {
        "title": "Memory Usage Warning",
        "description": "Memory usage is above 80%",
        "ruleType": "ALERT",
        "priority": "WARNING",
        "backToNormal": False,
        "threshold": 80.0,
        "metricValue": 83.0,
        "startedAt": "2026-03-29T11:00:00Z",
        "endedAt": None,
        "appName": "Backend Logs",
        "appType": "Logs",
        "alertRuleId": 22345,
        "tags": {},
        "url": "https://apps.sematext.com/ui/alerts/22345",
    }


def _recovery_event() -> dict:
    """Sematext webhook payload for a recovery (backToNormal=True)."""
    return {
        "title": "High CPU Usage",
        "description": "CPU usage is back to normal",
        "ruleType": "ALERT",
        "priority": "CRITICAL",
        "backToNormal": True,
        "threshold": 90.0,
        "metricValue": 45.0,
        "startedAt": "2026-03-29T10:00:00Z",
        "endedAt": "2026-03-29T10:30:00Z",
        "appName": "Production Monitoring",
        "appType": "Monitoring",
        "alertRuleId": 12345,
        "tags": {"env": "production"},
        "url": "https://apps.sematext.com/ui/alerts/12345",
    }


def _anomaly_event() -> dict:
    return {
        "title": "Anomaly Detected in Error Rate",
        "description": "Anomalous spike in error rate",
        "ruleType": "ANOMALY",
        "priority": "WARNING",
        "backToNormal": False,
        "threshold": None,
        "metricValue": None,
        "startedAt": "2026-03-29T09:00:00Z",
        "endedAt": None,
        "appName": "API Service",
        "appType": "Monitoring",
        "alertRuleId": 33345,
        "tags": {"service": "api"},
        "url": "https://apps.sematext.com/ui/alerts/33345",
    }


def _heartbeat_event() -> dict:
    return {
        "title": "Agent Heartbeat Missing",
        "description": "No heartbeat received from agent",
        "ruleType": "HEARTBEAT",
        "priority": "CRITICAL",
        "backToNormal": False,
        "threshold": None,
        "metricValue": None,
        "startedAt": "2026-03-29T08:00:00Z",
        "endedAt": None,
        "appName": "Edge Agent",
        "appType": "Monitoring",
        "alertRuleId": 44345,
        "tags": {},
        "url": "https://apps.sematext.com/ui/alerts/44345",
    }


def _scheduled_event() -> dict:
    return {
        "title": "Maintenance Window",
        "description": "Scheduled maintenance suppression",
        "ruleType": "SCHEDULED",
        "priority": "INFO",
        "backToNormal": False,
        "startedAt": "2026-03-29T07:00:00Z",
        "appName": "All Apps",
        "alertRuleId": 55345,
        "tags": {},
    }


def _numeric_priority_event(priority_value: str) -> dict:
    return {
        "title": f"Alert with numeric priority {priority_value}",
        "description": "Test numeric priority",
        "ruleType": "ALERT",
        "priority": priority_value,
        "backToNormal": False,
        "startedAt": "2026-03-29T06:00:00Z",
        "appName": "Test App",
        "alertRuleId": 66345,
        "tags": {},
    }


def _minimal_event() -> dict:
    """Minimal event with only required/essential fields."""
    return {
        "title": "Minimal Alert",
        "backToNormal": False,
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestSematextProviderConfig:
    def test_empty_auth_config_accepted(self):
        """Sematext webhook receiver requires no credentials."""
        provider = _make_provider()
        assert isinstance(provider.authentication_config, SematextProviderAuthConfig)

    def test_validate_config_does_not_raise(self):
        provider = _make_provider()
        # Should not raise
        provider.validate_config()


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


class TestStatusDerivation:
    def test_firing_when_not_back_to_normal(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.status == AlertStatus.FIRING

    def test_resolved_when_back_to_normal_true(self):
        dto = SematextProvider._format_alert(_recovery_event())
        assert dto.status == AlertStatus.RESOLVED

    def test_anomaly_fires(self):
        dto = SematextProvider._format_alert(_anomaly_event())
        assert dto.status == AlertStatus.FIRING

    def test_heartbeat_fires(self):
        dto = SematextProvider._format_alert(_heartbeat_event())
        assert dto.status == AlertStatus.FIRING

    def test_scheduled_suppressed(self):
        dto = SematextProvider._format_alert(_scheduled_event())
        assert dto.status == AlertStatus.SUPPRESSED

    def test_back_to_normal_overrides_rule_type(self):
        """backToNormal=True should resolve even for ANOMALY ruleType."""
        event = _anomaly_event()
        event["backToNormal"] = True
        dto = SematextProvider._format_alert(event)
        assert dto.status == AlertStatus.RESOLVED

    def test_unknown_rule_type_defaults_to_firing(self):
        event = _critical_alert_event()
        event["ruleType"] = "UNKNOWN_TYPE"
        dto = SematextProvider._format_alert(event)
        assert dto.status == AlertStatus.FIRING


# ---------------------------------------------------------------------------
# Severity derivation
# ---------------------------------------------------------------------------


class TestSeverityDerivation:
    def test_critical_priority_maps_to_critical(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.severity == AlertSeverity.CRITICAL

    def test_warning_priority_maps_to_warning(self):
        dto = SematextProvider._format_alert(_warning_alert_event())
        assert dto.severity == AlertSeverity.WARNING

    def test_info_priority_maps_to_info(self):
        event = _warning_alert_event()
        event["priority"] = "INFO"
        dto = SematextProvider._format_alert(event)
        assert dto.severity == AlertSeverity.INFO

    def test_error_priority_maps_to_high(self):
        event = _warning_alert_event()
        event["priority"] = "ERROR"
        dto = SematextProvider._format_alert(event)
        assert dto.severity == AlertSeverity.HIGH

    def test_low_priority_maps_to_low(self):
        event = _warning_alert_event()
        event["priority"] = "LOW"
        dto = SematextProvider._format_alert(event)
        assert dto.severity == AlertSeverity.LOW

    def test_unknown_priority_defaults_to_info(self):
        event = _warning_alert_event()
        event["priority"] = "UNKNOWN_PRIORITY"
        dto = SematextProvider._format_alert(event)
        assert dto.severity == AlertSeverity.INFO

    def test_numeric_priority_5_critical(self):
        dto = SematextProvider._format_alert(_numeric_priority_event("5"))
        assert dto.severity == AlertSeverity.CRITICAL

    def test_numeric_priority_4_high(self):
        dto = SematextProvider._format_alert(_numeric_priority_event("4"))
        assert dto.severity == AlertSeverity.HIGH

    def test_numeric_priority_3_warning(self):
        dto = SematextProvider._format_alert(_numeric_priority_event("3"))
        assert dto.severity == AlertSeverity.WARNING

    def test_numeric_priority_2_info(self):
        dto = SematextProvider._format_alert(_numeric_priority_event("2"))
        assert dto.severity == AlertSeverity.INFO

    def test_numeric_priority_1_low(self):
        dto = SematextProvider._format_alert(_numeric_priority_event("1"))
        assert dto.severity == AlertSeverity.LOW

    def test_recovery_caps_severity_to_info(self):
        """Even a CRITICAL alert should have INFO severity when it recovers."""
        dto = SematextProvider._format_alert(_recovery_event())
        assert dto.status == AlertStatus.RESOLVED
        assert dto.severity == AlertSeverity.INFO

    def test_priority_case_insensitive(self):
        event = _critical_alert_event()
        event["priority"] = "critical"
        dto = SematextProvider._format_alert(event)
        assert dto.severity == AlertSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Name and Description
# ---------------------------------------------------------------------------


class TestNameAndDescription:
    def test_name_from_title(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.name == "High CPU Usage"

    def test_description_from_description_field(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert "CPU usage exceeded threshold" in dto.description

    def test_description_includes_metric_context(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert "97.5" in dto.description
        assert "90.0" in dto.description

    def test_description_no_metric_context_when_none(self):
        dto = SematextProvider._format_alert(_anomaly_event())
        # anomaly_event has None for threshold and metricValue
        assert "Value:" not in dto.description

    def test_missing_title_defaults_to_sematext_alert(self):
        event = _minimal_event()
        del event["title"]
        dto = SematextProvider._format_alert(event)
        assert dto.name == "Sematext Alert"


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


class TestIdGeneration:
    def test_id_contains_rule_id_and_timestamp(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert "12345" in dto.id
        assert "2026-03-29" in dto.id

    def test_id_unique_per_rule(self):
        dto1 = SematextProvider._format_alert(_critical_alert_event())
        dto2 = SematextProvider._format_alert(_warning_alert_event())
        assert dto1.id != dto2.id

    def test_id_generated_without_rule_id(self):
        event = _minimal_event()
        # No alertRuleId
        dto = SematextProvider._format_alert(event)
        assert dto.id is not None
        assert len(dto.id) > 0


# ---------------------------------------------------------------------------
# Labels and Tags
# ---------------------------------------------------------------------------


class TestLabelsAndTags:
    def test_labels_include_rule_type(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.labels["ruleType"] == "ALERT"

    def test_labels_include_app_name_and_type(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.labels["appName"] == "Production Monitoring"
        assert dto.labels["appType"] == "Monitoring"

    def test_labels_include_alert_rule_id(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.labels["alertRuleId"] == "12345"

    def test_labels_include_back_to_normal(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.labels["backToNormal"] == "False"

    def test_sematext_tags_merged_into_labels(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.labels["tag_env"] == "production"
        assert dto.labels["tag_host"] == "prod-server-01"

    def test_empty_tags_dict_no_labels(self):
        dto = SematextProvider._format_alert(_warning_alert_event())
        # No tag_ keys expected when tags is {}
        tag_keys = [k for k in dto.labels if k.startswith("tag_")]
        assert len(tag_keys) == 0

    def test_service_is_app_name(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.service == "Production Monitoring"

    def test_source_is_sematext(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert "sematext" in dto.source

    def test_url_preserved(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert dto.url == "https://apps.sematext.com/ui/alerts/12345"


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


class TestTimestamps:
    def test_last_received_from_started_at(self):
        dto = SematextProvider._format_alert(_critical_alert_event())
        assert "2026-03-29" in dto.lastReceived

    def test_last_received_default_when_no_started_at(self):
        dto = SematextProvider._format_alert(_minimal_event())
        assert dto.lastReceived is not None
        assert len(dto.lastReceived) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_minimal_event_no_errors(self):
        """Minimal event with only backToNormal and title should not raise."""
        dto = SematextProvider._format_alert(_minimal_event())
        assert isinstance(dto, AlertDto)

    def test_none_tags_returns_alert_dto(self):
        """When Sematext sends tags=null, provider should return a valid AlertDto."""
        event = _critical_alert_event()
        event["tags"] = None
        dto = SematextProvider._format_alert(event)
        assert isinstance(dto, AlertDto)
        # tags=None means no tag_ labels should be added
        tag_keys = [k for k in dto.labels if k.startswith("tag_")]
        assert len(tag_keys) == 0

    def test_missing_priority_defaults_to_info_severity(self):
        event = _minimal_event()
        # No priority field
        dto = SematextProvider._format_alert(event)
        assert dto.severity == AlertSeverity.INFO

    def test_missing_rule_type_defaults_to_alert(self):
        event = _minimal_event()
        dto = SematextProvider._format_alert(event)
        assert dto.status == AlertStatus.FIRING


# ---------------------------------------------------------------------------
# Map completeness
# ---------------------------------------------------------------------------


class TestMapCompleteness:
    def test_severity_map_has_critical(self):
        assert SematextProvider.SEVERITY_MAP["critical"] == AlertSeverity.CRITICAL

    def test_severity_map_has_warning(self):
        assert SematextProvider.SEVERITY_MAP["warning"] == AlertSeverity.WARNING

    def test_severity_map_has_info(self):
        assert SematextProvider.SEVERITY_MAP["info"] == AlertSeverity.INFO

    def test_severity_map_numeric_complete(self):
        for i in range(1, 6):
            assert str(i) in SematextProvider.SEVERITY_MAP

    def test_rule_type_map_alert_fires(self):
        assert SematextProvider.RULE_TYPE_STATUS_MAP["ALERT"] == AlertStatus.FIRING

    def test_rule_type_map_recovery_resolves(self):
        assert SematextProvider.RULE_TYPE_STATUS_MAP["RECOVERY"] == AlertStatus.RESOLVED

    def test_rule_type_map_scheduled_suppresses(self):
        assert SematextProvider.RULE_TYPE_STATUS_MAP["SCHEDULED"] == AlertStatus.SUPPRESSED

    def test_rule_type_map_anomaly_fires(self):
        assert SematextProvider.RULE_TYPE_STATUS_MAP["ANOMALY"] == AlertStatus.FIRING

    def test_rule_type_map_heartbeat_fires(self):
        assert SematextProvider.RULE_TYPE_STATUS_MAP["HEARTBEAT"] == AlertStatus.FIRING
