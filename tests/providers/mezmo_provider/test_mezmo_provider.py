"""
Unit tests for the Mezmo (formerly LogDNA) provider.

Tests cover:
  - Config validation (no-op auth)
  - _format_alert: single alert object
  - _format_alert: multi-alert payload (alerts array)
  - _format_alert: flat single-alert (no alerts key)
  - Status derivation (resolved flag, ended_at)
  - Severity derivation (string variants, numeric syslog levels)
  - Recovery caps severity to INFO
  - Description enrichment with line count
  - Label and account mapping
  - ID generation
  - Edge cases: empty payload, missing fields
  - SEVERITY_MAP completeness
"""

import pytest
from unittest.mock import MagicMock

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.mezmo_provider.mezmo_provider import (
    MezmoProvider,
    MezmoProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider() -> MezmoProvider:
    """Build a MezmoProvider (no auth fields needed)."""
    config = ProviderConfig(authentication={})
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return MezmoProvider(ctx, "mezmo-test", config)


def _critical_alert_payload() -> dict:
    """Multi-alert payload with one CRITICAL alert."""
    return {
        "account": "mycompany",
        "alerts": [
            {
                "name": "Error Rate Spike",
                "description": "More than 100 errors in 5 minutes on production",
                "query": "level:error",
                "type": "presence",
                "lines": 127,
                "label": "production",
                "severity": "CRITICAL",
                "url": "https://app.mezmo.com/alerts/123",
                "triggered_at": "2026-03-29T10:00:00Z",
                "ended_at": None,
                "resolved": False,
            }
        ],
    }


def _warning_alert_payload() -> dict:
    return {
        "account": "staging-org",
        "alerts": [
            {
                "name": "High Latency Detected",
                "description": "API latency exceeds 500ms",
                "query": "app:api latency>500",
                "type": "absence",
                "lines": 45,
                "label": "staging",
                "severity": "WARNING",
                "url": "https://app.mezmo.com/alerts/456",
                "triggered_at": "2026-03-29T11:00:00Z",
                "ended_at": None,
                "resolved": False,
            }
        ],
    }


def _recovery_payload() -> dict:
    return {
        "account": "mycompany",
        "alerts": [
            {
                "name": "Error Rate Spike",
                "description": "Error rate returned to normal",
                "query": "level:error",
                "type": "presence",
                "lines": 2,
                "label": "production",
                "severity": "CRITICAL",
                "url": "https://app.mezmo.com/alerts/123",
                "triggered_at": "2026-03-29T10:00:00Z",
                "ended_at": "2026-03-29T10:30:00Z",
                "resolved": True,
            }
        ],
    }


def _multi_alert_payload() -> dict:
    return {
        "account": "bigcorp",
        "alerts": [
            {
                "name": "DB Connection Errors",
                "description": "Database connection errors spiking",
                "query": "level:error database",
                "type": "presence",
                "lines": 55,
                "label": "db-cluster",
                "severity": "ERROR",
                "url": "https://app.mezmo.com/alerts/789",
                "triggered_at": "2026-03-29T12:00:00Z",
                "ended_at": None,
                "resolved": False,
            },
            {
                "name": "Auth Service Down",
                "description": "No logs from auth service",
                "query": "app:auth-service",
                "type": "absence",
                "lines": 0,
                "label": "auth",
                "severity": "CRITICAL",
                "url": "https://app.mezmo.com/alerts/790",
                "triggered_at": "2026-03-29T12:01:00Z",
                "ended_at": None,
                "resolved": False,
            },
        ],
    }


def _flat_single_alert() -> dict:
    """Flat payload without an 'alerts' key."""
    return {
        "name": "Memory Alert",
        "description": "Memory usage above threshold",
        "query": "level:warn memory",
        "type": "presence",
        "lines": 30,
        "label": "backend",
        "severity": "WARN",
        "url": "https://app.mezmo.com/alerts/999",
        "triggered_at": "2026-03-29T09:00:00Z",
        "resolved": False,
    }


def _numeric_severity_payload(level: str) -> dict:
    return {
        "account": "test-org",
        "alerts": [
            {
                "name": f"Level {level} alert",
                "description": "Numeric severity test",
                "query": "app:test",
                "type": "presence",
                "lines": 1,
                "label": "test",
                "level": level,
                "url": "https://app.mezmo.com/alerts/num",
                "triggered_at": "2026-03-29T08:00:00Z",
                "resolved": False,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestMezmoProviderConfig:
    def test_empty_auth_accepted(self):
        provider = _make_provider()
        assert isinstance(provider.authentication_config, MezmoProviderAuthConfig)

    def test_validate_config_does_not_raise(self):
        provider = _make_provider()
        provider.validate_config()


# ---------------------------------------------------------------------------
# Single alert (multi-alert payload)
# ---------------------------------------------------------------------------


class TestFormatAlertSingle:
    def test_returns_alert_dto_for_single_alert(self):
        result = MezmoProvider._format_alert(_critical_alert_payload())
        assert isinstance(result, AlertDto)

    def test_critical_alert_is_firing(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.status == AlertStatus.FIRING

    def test_critical_severity_mapped(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.severity == AlertSeverity.CRITICAL

    def test_warning_severity_mapped(self):
        dto = MezmoProvider._format_alert(_warning_alert_payload())
        assert dto.severity == AlertSeverity.WARNING

    def test_name_from_alert_name(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.name == "Error Rate Spike"

    def test_description_from_field(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert "100 errors" in dto.description

    def test_description_includes_lines_count(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert "127" in dto.description

    def test_source_is_mezmo(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert "mezmo" in dto.source

    def test_url_preserved(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.url == "https://app.mezmo.com/alerts/123"

    def test_service_is_label(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.service == "production"

    def test_last_received_from_triggered_at(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert "2026-03-29" in dto.lastReceived

    def test_id_contains_account_and_name(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert "mycompany" in dto.id
        assert "error_rate_spike" in dto.id


# ---------------------------------------------------------------------------
# Multi-alert payload
# ---------------------------------------------------------------------------


class TestFormatAlertMulti:
    def test_multi_alert_returns_list(self):
        result = MezmoProvider._format_alert(_multi_alert_payload())
        assert isinstance(result, list)
        assert len(result) == 2

    def test_all_items_are_alert_dtos(self):
        result = MezmoProvider._format_alert(_multi_alert_payload())
        assert all(isinstance(r, AlertDto) for r in result)

    def test_first_alert_name(self):
        result = MezmoProvider._format_alert(_multi_alert_payload())
        assert result[0].name == "DB Connection Errors"

    def test_second_alert_name(self):
        result = MezmoProvider._format_alert(_multi_alert_payload())
        assert result[1].name == "Auth Service Down"

    def test_multi_alert_different_severities(self):
        result = MezmoProvider._format_alert(_multi_alert_payload())
        assert result[0].severity == AlertSeverity.HIGH   # ERROR
        assert result[1].severity == AlertSeverity.CRITICAL  # CRITICAL


# ---------------------------------------------------------------------------
# Flat single alert (no 'alerts' key)
# ---------------------------------------------------------------------------


class TestFlatSingleAlert:
    def test_flat_alert_returns_alert_dto(self):
        result = MezmoProvider._format_alert(_flat_single_alert())
        assert isinstance(result, AlertDto)

    def test_flat_alert_severity_warn(self):
        result = MezmoProvider._format_alert(_flat_single_alert())
        assert result.severity == AlertSeverity.WARNING  # WARN → WARNING

    def test_flat_alert_name(self):
        result = MezmoProvider._format_alert(_flat_single_alert())
        assert result.name == "Memory Alert"


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


class TestStatusDerivation:
    def test_firing_when_resolved_false(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.status == AlertStatus.FIRING

    def test_resolved_when_resolved_true(self):
        dto = MezmoProvider._format_alert(_recovery_payload())
        assert dto.status == AlertStatus.RESOLVED

    def test_resolved_when_ended_at_set(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["ended_at"] = "2026-03-29T10:30:00Z"
        payload["alerts"][0]["resolved"] = False
        dto = MezmoProvider._format_alert(payload)
        assert dto.status == AlertStatus.RESOLVED

    def test_recovery_severity_capped_to_info(self):
        dto = MezmoProvider._format_alert(_recovery_payload())
        assert dto.status == AlertStatus.RESOLVED
        assert dto.severity == AlertSeverity.INFO


# ---------------------------------------------------------------------------
# Severity: string variants
# ---------------------------------------------------------------------------


class TestSeverityStrings:
    def test_critical(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "CRITICAL"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.CRITICAL

    def test_fatal(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "fatal"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.CRITICAL

    def test_error(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "ERROR"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.HIGH

    def test_warn(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "WARN"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.WARNING

    def test_warning(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "WARNING"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.WARNING

    def test_info(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "INFO"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.INFO

    def test_debug(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "DEBUG"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.LOW

    def test_trace(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "trace"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.LOW

    def test_unknown_severity_defaults_to_info(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["severity"] = "UNKNOWN"
        assert MezmoProvider._format_alert(payload).severity == AlertSeverity.INFO


# ---------------------------------------------------------------------------
# Severity: numeric (syslog levels)
# ---------------------------------------------------------------------------


class TestNumericSyslogSeverity:
    def test_level_0_emergency_is_critical(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("0"))
        assert dto.severity == AlertSeverity.CRITICAL

    def test_level_1_alert_is_critical(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("1"))
        assert dto.severity == AlertSeverity.CRITICAL

    def test_level_2_critical_is_critical(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("2"))
        assert dto.severity == AlertSeverity.CRITICAL

    def test_level_3_error_is_high(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("3"))
        assert dto.severity == AlertSeverity.HIGH

    def test_level_4_warning_is_warning(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("4"))
        assert dto.severity == AlertSeverity.WARNING

    def test_level_5_notice_is_info(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("5"))
        assert dto.severity == AlertSeverity.INFO

    def test_level_6_info_is_info(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("6"))
        assert dto.severity == AlertSeverity.INFO

    def test_level_7_debug_is_low(self):
        dto = MezmoProvider._format_alert(_numeric_severity_payload("7"))
        assert dto.severity == AlertSeverity.LOW


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


class TestLabels:
    def test_labels_include_account(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.labels["account"] == "mycompany"

    def test_labels_include_query(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.labels["query"] == "level:error"

    def test_labels_include_alert_type(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.labels["alertType"] == "presence"

    def test_labels_include_label_field(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.labels["label"] == "production"

    def test_labels_include_resolved_flag(self):
        dto = MezmoProvider._format_alert(_critical_alert_payload())
        assert dto.labels["resolved"] == "False"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_name_defaults(self):
        payload = {"account": "test", "alerts": [{"resolved": False}]}
        dto = MezmoProvider._format_alert(payload)
        assert dto.name == "Mezmo Alert"

    def test_missing_lines_no_bracket_in_description(self):
        payload = _critical_alert_payload()
        del payload["alerts"][0]["lines"]
        dto = MezmoProvider._format_alert(payload)
        assert "Matched lines" not in dto.description

    def test_empty_alerts_array_returns_list(self):
        payload = {"account": "test", "alerts": []}
        result = MezmoProvider._format_alert(payload)
        # Empty list case
        assert result == [] or isinstance(result, list)

    def test_service_falls_back_to_account_when_no_label(self):
        payload = _critical_alert_payload()
        payload["alerts"][0]["label"] = ""
        dto = MezmoProvider._format_alert(payload)
        assert dto.service == "mycompany"


# ---------------------------------------------------------------------------
# SEVERITY_MAP completeness
# ---------------------------------------------------------------------------


class TestSeverityMapCompleteness:
    def test_critical_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["critical"] == AlertSeverity.CRITICAL

    def test_fatal_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["fatal"] == AlertSeverity.CRITICAL

    def test_error_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["error"] == AlertSeverity.HIGH

    def test_warn_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["warn"] == AlertSeverity.WARNING

    def test_warning_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["warning"] == AlertSeverity.WARNING

    def test_info_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["info"] == AlertSeverity.INFO

    def test_debug_in_map(self):
        assert MezmoProvider.SEVERITY_MAP["debug"] == AlertSeverity.LOW

    def test_numeric_0_to_7_all_in_map(self):
        for i in range(8):
            assert str(i) in MezmoProvider.SEVERITY_MAP
