"""
Tests for the Sematext Cloud provider.
"""

import hashlib
from datetime import datetime, timezone

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.sematext_provider.sematext_provider import (
    SematextProvider,
    _build_alert_id,
    _build_labels,
    _derive_severity,
    _is_back_to_normal,
)


# ── Fixtures ─────────────────────────────────────────────────────────

def _base_event(**overrides) -> dict:
    """Return a realistic Sematext webhook payload."""
    event = {
        "backToNormal": "false",
        "ruleType": "AF_VALUE",
        "description": "CPU usage exceeded 90%",
        "title": "High CPU Alert",
        "applicationId": "12345",
        "url": "https://hooks.sematext.com/example",
        "createTimestamp": "2025-01-15T12:00:00Z",
        "troubleshootUrl": "https://apps.sematext.com/ui/alerts/12345",
    }
    event.update(overrides)
    return event


# ── _is_back_to_normal ──────────────────────────────────────────────

class TestIsBackToNormal:
    def test_string_false(self):
        assert _is_back_to_normal({"backToNormal": "false"}) is False

    def test_string_true(self):
        assert _is_back_to_normal({"backToNormal": "true"}) is True

    def test_string_true_upper(self):
        assert _is_back_to_normal({"backToNormal": "True"}) is True

    def test_bool_false(self):
        assert _is_back_to_normal({"backToNormal": False}) is False

    def test_bool_true(self):
        assert _is_back_to_normal({"backToNormal": True}) is True

    def test_missing_key(self):
        assert _is_back_to_normal({}) is False

    def test_none_value(self):
        assert _is_back_to_normal({"backToNormal": None}) is False


# ── _derive_severity ────────────────────────────────────────────────

class TestDeriveSeverity:
    # With explicit priority field
    def test_priority_critical_string(self):
        assert _derive_severity({"priority": "CRITICAL"}, False) == AlertSeverity.CRITICAL

    def test_priority_error_string(self):
        assert _derive_severity({"priority": "ERROR"}, False) == AlertSeverity.HIGH

    def test_priority_warning_string(self):
        assert _derive_severity({"priority": "WARNING"}, False) == AlertSeverity.WARNING

    def test_priority_info_string(self):
        assert _derive_severity({"priority": "INFO"}, False) == AlertSeverity.INFO

    def test_priority_low_string(self):
        assert _derive_severity({"priority": "LOW"}, False) == AlertSeverity.LOW

    def test_priority_case_insensitive(self):
        assert _derive_severity({"priority": "critical"}, False) == AlertSeverity.CRITICAL

    def test_priority_mixed_case(self):
        assert _derive_severity({"priority": "Warning"}, False) == AlertSeverity.WARNING

    def test_priority_int_5(self):
        assert _derive_severity({"priority": 5}, False) == AlertSeverity.CRITICAL

    def test_priority_int_4(self):
        assert _derive_severity({"priority": 4}, False) == AlertSeverity.HIGH

    def test_priority_int_3(self):
        assert _derive_severity({"priority": 3}, False) == AlertSeverity.WARNING

    def test_priority_int_2(self):
        assert _derive_severity({"priority": 2}, False) == AlertSeverity.INFO

    def test_priority_int_1(self):
        assert _derive_severity({"priority": 1}, False) == AlertSeverity.LOW

    def test_priority_numeric_string(self):
        assert _derive_severity({"priority": "5"}, False) == AlertSeverity.CRITICAL

    # Without priority, based on rule type / back-to-normal
    def test_back_to_normal_defaults_to_info(self):
        assert _derive_severity({}, True) == AlertSeverity.INFO

    def test_anomaly_rule_type(self):
        assert (
            _derive_severity({"ruleType": "AF_ANOMALY_VALUE"}, False)
            == AlertSeverity.WARNING
        )

    def test_log_anomaly_rule_type(self):
        assert (
            _derive_severity({"ruleType": "LOGSENE_ANOMALY_VALUE"}, False)
            == AlertSeverity.WARNING
        )

    def test_rum_anomaly_rule_type(self):
        assert (
            _derive_severity({"ruleType": "RUM_ANOMALY_VALUE"}, False)
            == AlertSeverity.WARNING
        )

    def test_threshold_rule_defaults_to_high(self):
        assert (
            _derive_severity({"ruleType": "AF_VALUE"}, False) == AlertSeverity.HIGH
        )

    def test_heartbeat_rule_defaults_to_high(self):
        assert (
            _derive_severity({"ruleType": "HEARTBEAT"}, False) == AlertSeverity.HIGH
        )

    def test_unknown_priority_falls_through(self):
        # Unknown string priority falls through to rule-type logic
        assert (
            _derive_severity({"priority": "UNKNOWN", "ruleType": "AF_VALUE"}, False)
            == AlertSeverity.HIGH
        )


# ── _build_alert_id ─────────────────────────────────────────────────

class TestBuildAlertId:
    def test_deterministic(self):
        event = _base_event()
        assert _build_alert_id(event) == _build_alert_id(event)

    def test_different_app_id_gives_different_id(self):
        e1 = _base_event(applicationId="111")
        e2 = _base_event(applicationId="222")
        assert _build_alert_id(e1) != _build_alert_id(e2)

    def test_includes_filters_in_id(self):
        e1 = _base_event(filters={"os.host": "host-a"})
        e2 = _base_event(filters={"os.host": "host-b"})
        assert _build_alert_id(e1) != _build_alert_id(e2)

    def test_no_filters_still_works(self):
        event = _base_event()
        assert isinstance(_build_alert_id(event), str)
        assert len(_build_alert_id(event)) == 64  # SHA-256 hex length

    def test_missing_fields(self):
        # Minimal event with none of the expected fields
        event = {}
        alert_id = _build_alert_id(event)
        assert isinstance(alert_id, str) and len(alert_id) == 64


# ── _build_labels ───────────────────────────────────────────────────

class TestBuildLabels:
    def test_basic_labels(self):
        event = _base_event()
        labels = _build_labels(event)
        assert labels["applicationId"] == "12345"
        assert labels["ruleType"] == "AF_VALUE"

    def test_filters_become_labels(self):
        event = _base_event(filters={"os.host": "web-01", "region": "us-east"})
        labels = _build_labels(event)
        assert labels["filter_os.host"] == "web-01"
        assert labels["filter_region"] == "us-east"

    def test_tags_become_labels(self):
        event = _base_event(tags={"env": "production", "team": "infra"})
        labels = _build_labels(event)
        assert labels["tag_env"] == "production"
        assert labels["tag_team"] == "infra"

    def test_no_filters_or_tags(self):
        event = {"ruleType": "HEARTBEAT"}
        labels = _build_labels(event)
        assert "filter_" not in str(labels)
        assert "tag_" not in str(labels)

    def test_none_tags(self):
        event = _base_event(tags=None)
        labels = _build_labels(event)
        assert "tag_" not in str(labels)


# ── SematextProvider._format_alert ──────────────────────────────────

class TestFormatAlert:
    def test_firing_alert(self):
        event = _base_event()
        alert = SematextProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.name == "High CPU Alert"
        assert alert.description == "CPU usage exceeded 90%"
        assert alert.source == ["sematext"]

    def test_resolved_alert_bool(self):
        event = _base_event(backToNormal=True)
        alert = SematextProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_resolved_alert_string(self):
        event = _base_event(backToNormal="true")
        alert = SematextProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_severity_from_priority(self):
        event = _base_event(priority="CRITICAL")
        alert = SematextProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL

    def test_severity_default_high_for_threshold(self):
        event = _base_event()
        alert = SematextProvider._format_alert(event)
        assert alert.severity == AlertSeverity.HIGH

    def test_severity_warning_for_anomaly(self):
        event = _base_event(ruleType="AF_ANOMALY_VALUE")
        alert = SematextProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING

    def test_url_uses_troubleshoot_url(self):
        event = _base_event()
        alert = SematextProvider._format_alert(event)
        assert str(alert.url) == "https://apps.sematext.com/ui/alerts/12345"

    def test_url_falls_back_to_url(self):
        event = _base_event()
        del event["troubleshootUrl"]
        alert = SematextProvider._format_alert(event)
        assert str(alert.url) == "https://hooks.sematext.com/example"

    def test_labels_populated(self):
        event = _base_event(
            filters={"os.host": "web-01"},
            tags={"env": "prod"},
        )
        alert = SematextProvider._format_alert(event)
        assert alert.labels["applicationId"] == "12345"
        assert alert.labels["filter_os.host"] == "web-01"
        assert alert.labels["tag_env"] == "prod"

    def test_timestamp_passed_through(self):
        event = _base_event(createTimestamp="2025-06-01T08:30:00Z")
        alert = SematextProvider._format_alert(event)
        assert "2025-06-01" in alert.lastReceived

    def test_missing_timestamp_defaults_to_now(self):
        event = _base_event()
        del event["createTimestamp"]
        alert = SematextProvider._format_alert(event)
        # Should not raise; lastReceived should be a valid ISO timestamp
        assert alert.lastReceived is not None

    def test_default_title(self):
        event = _base_event()
        del event["title"]
        alert = SematextProvider._format_alert(event)
        assert alert.name == "Sematext Alert"

    def test_minimal_event(self):
        # Edge case: nearly empty payload
        event = {}
        alert = SematextProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING
        assert alert.name == "Sematext Alert"
        assert alert.source == ["sematext"]

    def test_heartbeat_alert(self):
        event = _base_event(ruleType="HEARTBEAT")
        alert = SematextProvider._format_alert(event)
        assert alert.labels["ruleType"] == "HEARTBEAT"
        assert alert.severity == AlertSeverity.HIGH

    def test_synthetics_alert(self):
        event = _base_event(ruleType="SYNTHETICS_RESULT_VALUE")
        alert = SematextProvider._format_alert(event)
        assert alert.labels["ruleType"] == "SYNTHETICS_RESULT_VALUE"

    def test_fingerprint_generated(self):
        event = _base_event()
        alert = SematextProvider._format_alert(event)
        assert alert.fingerprint is not None
        assert len(alert.fingerprint) > 0

    def test_group_by_filters_create_unique_fingerprints(self):
        e1 = _base_event(filters={"os.host": "host-a"})
        e2 = _base_event(filters={"os.host": "host-b"})
        a1 = SematextProvider._format_alert(e1)
        a2 = SematextProvider._format_alert(e2)
        # The alert IDs are different, so fingerprints should differ
        assert a1.id != a2.id


# ── Provider class properties ───────────────────────────────────────

class TestProviderMetadata:
    def test_display_name(self):
        assert SematextProvider.PROVIDER_DISPLAY_NAME == "Sematext"

    def test_tags(self):
        assert "alert" in SematextProvider.PROVIDER_TAGS

    def test_category(self):
        assert "Monitoring" in SematextProvider.PROVIDER_CATEGORY

    def test_fingerprint_fields(self):
        assert SematextProvider.FINGERPRINT_FIELDS == ["id"]

    def test_webhook_markdown_present(self):
        assert "keep_webhook_api_url" in SematextProvider.webhook_markdown
        assert "api_key" in SematextProvider.webhook_markdown
