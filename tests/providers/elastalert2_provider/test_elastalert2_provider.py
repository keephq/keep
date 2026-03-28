"""
Unit tests for the ElastAlert2 provider.

Tests verify:
  - Alert formatting from ElastAlert2 HTTP POST payloads
  - Severity mapping (alert_priority, log.level, level, severity)
  - Description with num_hits context
  - Timestamp handling (valid ISO8601, Z suffix, missing)
  - Source field is set to ["elastalert2"]
  - Labels preservation from the source event
  - validate_config() accepts empty config (no credentials required)
"""

import pytest
from unittest.mock import MagicMock

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.elastalert2_provider.elastalert2_provider import (
    Elastalert2Provider,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider() -> Elastalert2Provider:
    config = ProviderConfig(authentication={})
    ctx = ContextManager(tenant_id="test", workflow_id="test")
    return Elastalert2Provider(ctx, "elastalert2-test", config)


def _basic_event(**kwargs) -> dict:
    base = {
        "rule_name": "TestRule",
        "alert_text": "Test alert fired",
        "num_hits": 10,
        "num_matches": 1,
        "@timestamp": "2024-01-15T10:30:00Z",
        "log.level": "warning",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestElastAlert2Config:
    def test_empty_auth_accepted(self):
        """ElastAlert2 provider needs no credentials — empty config must pass."""
        provider = _make_provider()
        provider.validate_config()  # should not raise

    def test_provider_created_successfully(self):
        provider = _make_provider()
        assert provider is not None


# ---------------------------------------------------------------------------
# _format_alert — basic cases
# ---------------------------------------------------------------------------


class TestElastAlert2FormatAlert:
    def test_basic_alert_structure(self):
        event = _basic_event()
        result = Elastalert2Provider._format_alert(event)
        assert isinstance(result, AlertDto)
        assert result.name == "TestRule"
        assert result.status == AlertStatus.FIRING
        assert result.source == ["elastalert2"]

    def test_description_includes_num_hits(self):
        event = _basic_event(num_hits=42)
        result = Elastalert2Provider._format_alert(event)
        assert "42" in result.description

    def test_description_without_num_hits(self):
        event = _basic_event()
        event.pop("num_hits")
        result = Elastalert2Provider._format_alert(event)
        assert result.description == "Test alert fired"

    def test_name_defaults_to_elastalert2_if_missing(self):
        result = Elastalert2Provider._format_alert({})
        assert result.name == "elastalert2"

    def test_source_always_elastalert2(self):
        result = Elastalert2Provider._format_alert(_basic_event())
        assert result.source == ["elastalert2"]

    def test_fingerprint_is_set(self):
        result = Elastalert2Provider._format_alert(_basic_event())
        assert result.fingerprint is not None
        assert len(result.fingerprint) > 0


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------


class TestElastAlert2SeverityMapping:
    @pytest.mark.parametrize(
        "level,expected",
        [
            ("critical", AlertSeverity.CRITICAL),
            ("error", AlertSeverity.HIGH),
            ("high", AlertSeverity.HIGH),
            ("warn", AlertSeverity.WARNING),
            ("warning", AlertSeverity.WARNING),
            ("medium", AlertSeverity.WARNING),
            ("info", AlertSeverity.INFO),
            ("information", AlertSeverity.INFO),
            ("low", AlertSeverity.LOW),
            ("debug", AlertSeverity.LOW),
        ],
    )
    def test_log_level_mapping(self, level, expected):
        event = _basic_event()
        event["log.level"] = level
        result = Elastalert2Provider._format_alert(event)
        assert result.severity == expected

    @pytest.mark.parametrize(
        "priority,expected",
        [
            (1, AlertSeverity.CRITICAL),
            (2, AlertSeverity.HIGH),
            (3, AlertSeverity.WARNING),
            (4, AlertSeverity.INFO),
            (5, AlertSeverity.LOW),
        ],
    )
    def test_alert_priority_mapping(self, priority, expected):
        event = {
            "rule_name": "PriorityTest",
            "alert_text": "test",
            "alert_priority": priority,
        }
        result = Elastalert2Provider._format_alert(event)
        assert result.severity == expected

    def test_unknown_severity_defaults_to_info(self):
        event = _basic_event()
        event["log.level"] = "completely_unknown"
        result = Elastalert2Provider._format_alert(event)
        assert result.severity == AlertSeverity.INFO

    def test_missing_severity_defaults_to_info(self):
        event = {"rule_name": "NoSeverity", "alert_text": "hello"}
        result = Elastalert2Provider._format_alert(event)
        assert result.severity == AlertSeverity.INFO

    def test_level_field_used_when_log_level_absent(self):
        event = {"rule_name": "R", "alert_text": "t", "level": "error"}
        result = Elastalert2Provider._format_alert(event)
        assert result.severity == AlertSeverity.HIGH

    def test_severity_field_used(self):
        event = {"rule_name": "R", "alert_text": "t", "severity": "critical"}
        result = Elastalert2Provider._format_alert(event)
        assert result.severity == AlertSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Timestamp handling
# ---------------------------------------------------------------------------


class TestElastAlert2Timestamps:
    def test_valid_iso_timestamp(self):
        event = _basic_event(**{"@timestamp": "2024-06-01T12:00:00Z"})
        result = Elastalert2Provider._format_alert(event)
        assert "2024-06-01" in result.lastReceived

    def test_timestamp_without_z(self):
        event = _basic_event(**{"@timestamp": "2024-06-01T12:00:00+00:00"})
        result = Elastalert2Provider._format_alert(event)
        assert result.lastReceived is not None

    def test_missing_timestamp_falls_back_to_now(self):
        event = {"rule_name": "R", "alert_text": "t"}
        result = Elastalert2Provider._format_alert(event)
        assert result.lastReceived is not None

    def test_invalid_timestamp_falls_back_to_now(self):
        event = _basic_event(**{"@timestamp": "not-a-date"})
        result = Elastalert2Provider._format_alert(event)
        assert result.lastReceived is not None

    def test_fallback_timestamp_field(self):
        event = {"rule_name": "R", "alert_text": "t", "timestamp": "2024-07-04T00:00:00Z"}
        result = Elastalert2Provider._format_alert(event)
        assert "2024-07-04" in result.lastReceived


# ---------------------------------------------------------------------------
# Labels preservation
# ---------------------------------------------------------------------------


class TestElastAlert2Labels:
    def test_extra_fields_preserved_in_labels(self):
        event = _basic_event(host_name="prod-01", environment="production")
        result = Elastalert2Provider._format_alert(event)
        assert result.labels.get("environment") == "production"
        assert result.labels.get("host_name") == "prod-01"

    def test_internal_fields_excluded_from_labels(self):
        event = _basic_event()
        result = Elastalert2Provider._format_alert(event)
        for excluded in ("rule_name", "alert_text", "alert_text_type", "num_hits", "num_matches"):
            assert excluded not in (result.labels or {})

    def test_nested_values_excluded_from_labels(self):
        event = _basic_event()
        event["nested_dict"] = {"key": "value"}
        event["nested_list"] = ["a", "b"]
        result = Elastalert2Provider._format_alert(event)
        assert "nested_dict" not in (result.labels or {})
        assert "nested_list" not in (result.labels or {})


# ---------------------------------------------------------------------------
# Severity map coverage
# ---------------------------------------------------------------------------


class TestElastAlert2SeverityMap:
    def test_all_priority_levels_present(self):
        for i in range(1, 6):
            assert str(i) in Elastalert2Provider.SEVERITIES_MAP

    def test_all_text_levels_present(self):
        expected_keys = {
            "critical", "error", "high", "warn", "warning", "medium",
            "info", "information", "low", "debug",
        }
        assert expected_keys.issubset(Elastalert2Provider.SEVERITIES_MAP.keys())


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------


class TestElastAlert2Metadata:
    def test_display_name(self):
        assert Elastalert2Provider.PROVIDER_DISPLAY_NAME == "ElastAlert2"

    def test_category_includes_monitoring(self):
        assert "Monitoring" in Elastalert2Provider.PROVIDER_CATEGORY

    def test_fingerprint_fields(self):
        assert "rule_name" in Elastalert2Provider.FINGERPRINT_FIELDS
