"""
Comprehensive tests for SensuProvider.

Covers:
  - Auth config validation (API key, basic auth, missing creds)
  - _event_to_alert_dto_static: severity mapping, status mapping, silenced,
    timestamp handling, label extraction, environment/service, OK event skip
  - _format_alert (push/webhook path)
  - _get_alerts (pull path filtering)
  - _get_auth_headers (API key vs bearer token)
  - validate_scopes success + failure
  - SEVERITY_MAP and STATE_MAP completeness
  - Edge cases: missing fields, empty payloads, unknown status codes
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.sensu_provider.sensu_provider import (
    SensuProvider,
    SensuProviderAuthConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    return ContextManager(tenant_id="test", workflow_id="test")


@pytest.fixture
def api_key_config():
    return ProviderConfig(
        description="Sensu test",
        authentication={
            "sensu_host": "http://sensu.example.com:8080",
            "api_key": "test-api-key-1234",
        },
    )


@pytest.fixture
def basic_auth_config():
    return ProviderConfig(
        description="Sensu basic auth",
        authentication={
            "sensu_host": "http://sensu.example.com:8080",
            "username": "admin",
            "password": "secret",
        },
    )


@pytest.fixture
def provider(ctx, api_key_config):
    p = SensuProvider(ctx, "sensu-test", api_key_config)
    p.validate_config()
    return p


def _make_event(
    status_code=1,
    state="failing",
    check_name="cpu-check",
    entity_name="web01",
    namespace="default",
    is_silenced=False,
    output="CPU at 95%",
    entity_labels=None,
    check_labels=None,
    occurrences=3,
    timestamp=1700000000,
    event_id="abc-123",
    system_hostname=None,
):
    """Build a minimal but realistic Sensu event dict."""
    return {
        "id": event_id,
        "timestamp": timestamp,
        "metadata": {"namespace": namespace},
        "check": {
            "metadata": {
                "name": check_name,
                "namespace": namespace,
                "labels": check_labels or {},
            },
            "status": status_code,
            "state": state,
            "is_silenced": is_silenced,
            "output": output,
            "occurrences": occurrences,
        },
        "entity": {
            "metadata": {
                "name": entity_name,
                "namespace": namespace,
                "labels": entity_labels or {},
            },
            "system": {"hostname": system_hostname or entity_name},
        },
    }


# ---------------------------------------------------------------------------
# Auth config validation
# ---------------------------------------------------------------------------


class TestSensuAuthConfig:
    def test_api_key_only_is_valid(self, ctx, api_key_config):
        p = SensuProvider(ctx, "s", api_key_config)
        p.validate_config()  # no exception
        assert p.authentication_config.api_key == "test-api-key-1234"

    def test_basic_auth_is_valid(self, ctx, basic_auth_config):
        p = SensuProvider(ctx, "s", basic_auth_config)
        p.validate_config()
        assert p.authentication_config.username == "admin"

    def test_no_credentials_raises(self, ctx):
        cfg = ProviderConfig(
            description="x",
            authentication={"sensu_host": "http://sensu.example.com:8080"},
        )
        p = SensuProvider(ctx, "s", cfg)
        with pytest.raises(ValueError, match="api_key"):
            p.validate_config()

    def test_default_namespace_is_default(self, ctx, api_key_config):
        p = SensuProvider(ctx, "s", api_key_config)
        p.validate_config()
        assert p.authentication_config.namespace == "default"

    def test_custom_namespace(self, ctx):
        cfg = ProviderConfig(
            description="x",
            authentication={
                "sensu_host": "http://sensu.example.com:8080",
                "api_key": "k",
                "namespace": "production",
            },
        )
        p = SensuProvider(ctx, "s", cfg)
        p.validate_config()
        assert p.authentication_config.namespace == "production"

    def test_pull_all_namespaces_default_false(self, ctx, api_key_config):
        p = SensuProvider(ctx, "s", api_key_config)
        p.validate_config()
        assert p.authentication_config.pull_all_namespaces is False


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------


class TestSeverityMap:
    def test_status_0_maps_to_info(self):
        assert SensuProvider.SEVERITY_MAP[0] == AlertSeverity.INFO

    def test_status_1_maps_to_warning(self):
        assert SensuProvider.SEVERITY_MAP[1] == AlertSeverity.WARNING

    def test_status_2_maps_to_critical(self):
        assert SensuProvider.SEVERITY_MAP[2] == AlertSeverity.CRITICAL

    def test_unknown_status_codes_fall_back_to_high(self):
        for code in (3, 4, 10, 127):
            severity = SensuProvider.SEVERITY_MAP.get(code, AlertSeverity.HIGH)
            assert severity == AlertSeverity.HIGH

    def test_format_alert_warning_severity(self):
        event = _make_event(status_code=1)
        alert = SensuProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING

    def test_format_alert_critical_severity(self):
        event = _make_event(status_code=2)
        alert = SensuProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_unknown_status_code_3(self):
        event = _make_event(status_code=3)
        alert = SensuProvider._format_alert(event)
        assert alert.severity == AlertSeverity.HIGH

    def test_format_alert_unknown_status_code_127(self):
        event = _make_event(status_code=127)
        alert = SensuProvider._format_alert(event)
        assert alert.severity == AlertSeverity.HIGH


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------


class TestStatusMap:
    def test_state_map_passing_resolved(self):
        assert SensuProvider.STATE_MAP["passing"] == AlertStatus.RESOLVED

    def test_state_map_failing_firing(self):
        assert SensuProvider.STATE_MAP["failing"] == AlertStatus.FIRING

    def test_state_map_flapping_firing(self):
        assert SensuProvider.STATE_MAP["flapping"] == AlertStatus.FIRING

    def test_ok_status_code_resolves(self):
        event = _make_event(status_code=0)
        alert = SensuProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_failing_state_fires(self):
        event = _make_event(status_code=1, state="failing")
        alert = SensuProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING

    def test_flapping_state_fires(self):
        event = _make_event(status_code=1, state="flapping")
        alert = SensuProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING

    def test_silenced_event_is_suppressed(self):
        event = _make_event(status_code=1, is_silenced=True)
        alert = SensuProvider._format_alert(event)
        assert alert.status == AlertStatus.SUPPRESSED

    def test_silenced_overrides_severity_mapping(self):
        # Even a CRITICAL silenced event becomes SUPPRESSED (not FIRING)
        event = _make_event(status_code=2, is_silenced=True)
        alert = SensuProvider._format_alert(event)
        assert alert.status == AlertStatus.SUPPRESSED
        assert alert.severity == AlertSeverity.CRITICAL

    def test_unknown_state_defaults_to_firing(self):
        event = _make_event(status_code=1, state="unexpected_state")
        alert = SensuProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------


class TestFieldExtraction:
    def test_check_name_extracted(self):
        event = _make_event(check_name="disk-check")
        alert = SensuProvider._format_alert(event)
        assert alert.name == "disk-check"

    def test_entity_name_extracted(self):
        event = _make_event(entity_name="db-server-01")
        alert = SensuProvider._format_alert(event)
        assert alert.entity == "db-server-01"

    def test_namespace_extracted(self):
        event = _make_event(namespace="production")
        alert = SensuProvider._format_alert(event)
        assert alert.namespace == "production"

    def test_output_used_as_description(self):
        event = _make_event(output="Disk usage at 92%")
        alert = SensuProvider._format_alert(event)
        assert alert.description == "Disk usage at 92%"

    def test_output_whitespace_stripped(self):
        event = _make_event(output="  alert message  \n")
        alert = SensuProvider._format_alert(event)
        assert alert.description == "alert message"

    def test_event_id_used(self):
        event = _make_event(event_id="event-xyz-789")
        alert = SensuProvider._format_alert(event)
        assert alert.id == "event-xyz-789"

    def test_missing_event_id_uses_entity_check(self):
        event = _make_event(entity_name="host1", check_name="cpu")
        del event["id"]
        alert = SensuProvider._format_alert(event)
        assert alert.id == "host1:cpu"

    def test_occurrences_extracted(self):
        event = _make_event(occurrences=7)
        alert = SensuProvider._format_alert(event)
        assert alert.occurrences == 7

    def test_is_silenced_field(self):
        event = _make_event(is_silenced=True)
        alert = SensuProvider._format_alert(event)
        assert alert.is_silenced is True

    def test_source_is_sensu(self):
        event = _make_event()
        alert = SensuProvider._format_alert(event)
        assert "sensu" in alert.source

    def test_hostname_from_system(self):
        event = _make_event(system_hostname="web01.example.com")
        alert = SensuProvider._format_alert(event)
        assert alert.hostname == "web01.example.com"

    def test_hostname_fallback_to_entity_name(self):
        event = _make_event(entity_name="db01")
        # Remove system hostname
        event["entity"]["system"] = {}
        alert = SensuProvider._format_alert(event)
        assert alert.hostname == "db01"


# ---------------------------------------------------------------------------
# Timestamp handling
# ---------------------------------------------------------------------------


class TestTimestampHandling:
    def test_unix_timestamp_converted_to_utc(self):
        event = _make_event(timestamp=1700000000)
        alert = SensuProvider._format_alert(event)
        expected = datetime.datetime.fromtimestamp(
            1700000000, tz=datetime.timezone.utc
        )
        assert alert.lastReceived == expected

    def test_zero_timestamp_uses_now(self):
        event = _make_event(timestamp=0)
        before = datetime.datetime.now(tz=datetime.timezone.utc)
        alert = SensuProvider._format_alert(event)
        after = datetime.datetime.now(tz=datetime.timezone.utc)
        assert before <= alert.lastReceived <= after

    def test_missing_timestamp_uses_now(self):
        event = _make_event()
        del event["timestamp"]
        before = datetime.datetime.now(tz=datetime.timezone.utc)
        alert = SensuProvider._format_alert(event)
        after = datetime.datetime.now(tz=datetime.timezone.utc)
        assert before <= alert.lastReceived <= after


# ---------------------------------------------------------------------------
# Label and environment/service extraction
# ---------------------------------------------------------------------------


class TestLabelExtraction:
    def test_environment_extracted_from_entity_labels(self):
        event = _make_event(entity_labels={"environment": "staging"})
        alert = SensuProvider._format_alert(event)
        assert alert.environment == "staging"

    def test_env_shorthand_extracted(self):
        event = _make_event(entity_labels={"env": "prod"})
        alert = SensuProvider._format_alert(event)
        assert alert.environment == "prod"

    def test_environment_label_not_in_extra_labels(self):
        event = _make_event(entity_labels={"environment": "staging", "team": "ops"})
        alert = SensuProvider._format_alert(event)
        # 'environment' should be consumed, not left in labels
        assert "environment" not in (alert.labels or {})

    def test_service_from_entity_labels(self):
        event = _make_event(entity_labels={"service": "api-gateway"})
        alert = SensuProvider._format_alert(event)
        assert alert.service == "api-gateway"

    def test_service_fallback_to_entity_name(self):
        event = _make_event(entity_name="cache-server")
        alert = SensuProvider._format_alert(event)
        assert alert.service == "cache-server"

    def test_check_labels_merged_with_entity_labels(self):
        event = _make_event(
            entity_labels={"region": "us-east-1"},
            check_labels={"priority": "high"},
        )
        alert = SensuProvider._format_alert(event)
        remaining = alert.labels or {}
        assert remaining.get("region") == "us-east-1"
        assert remaining.get("priority") == "high"

    def test_environment_fallback_to_namespace(self):
        event = _make_event(namespace="prod-ns")
        alert = SensuProvider._format_alert(event)
        # No environment label -> falls back to namespace
        assert alert.environment == "prod-ns"


# ---------------------------------------------------------------------------
# Empty / edge-case payloads
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_event_does_not_raise(self):
        alert = SensuProvider._format_alert({})
        assert alert.name == "unknown"

    def test_missing_check_defaults(self):
        event = {"entity": {}, "metadata": {}}
        alert = SensuProvider._format_alert(event)
        assert alert.status_code == 0
        assert alert.severity == AlertSeverity.INFO

    def test_missing_entity_defaults(self):
        event = {
            "check": {"status": 1, "metadata": {"name": "cpu"}, "state": "failing"},
            "metadata": {},
        }
        alert = SensuProvider._format_alert(event)
        assert alert.entity == "unknown"

    def test_empty_output_uses_check_name_as_description(self):
        event = _make_event(output="", check_name="mem-check")
        alert = SensuProvider._format_alert(event)
        assert alert.description == "mem-check"

    def test_none_labels_dont_crash(self):
        event = _make_event()
        event["entity"]["metadata"]["labels"] = None
        event["check"]["metadata"]["labels"] = None
        alert = SensuProvider._format_alert(event)
        assert alert is not None


# ---------------------------------------------------------------------------
# Pull mode: _get_alerts filters OK events
# ---------------------------------------------------------------------------


class TestGetAlerts:
    def test_ok_events_filtered_out(self, provider):
        events = [
            _make_event(status_code=0, event_id="ok-1"),
            _make_event(status_code=1, event_id="warn-1"),
            _make_event(status_code=2, event_id="crit-1"),
        ]
        with patch.object(provider, "_get_events", return_value=events):
            alerts = provider._get_alerts()
        ids = [a.id for a in alerts]
        assert "ok-1" not in ids
        assert "warn-1" in ids
        assert "crit-1" in ids

    def test_all_ok_events_returns_empty(self, provider):
        events = [_make_event(status_code=0) for _ in range(5)]
        with patch.object(provider, "_get_events", return_value=events):
            alerts = provider._get_alerts()
        assert alerts == []

    def test_bad_event_is_skipped_not_raised(self, provider):
        bad_event = {"bad": "data"}
        good_event = _make_event(status_code=1, event_id="good-1")
        with patch.object(provider, "_get_events", return_value=[bad_event, good_event]):
            alerts = provider._get_alerts()
        assert len(alerts) == 1
        assert alerts[0].id == "good-1"

    def test_namespace_endpoint_used_by_default(self, provider):
        with patch.object(provider, "_api_get", return_value=[]) as mock_get:
            provider._get_events()
        called_endpoint = mock_get.call_args[0][0]
        assert "namespaces/default" in called_endpoint

    def test_all_namespaces_endpoint_used(self, ctx):
        cfg = ProviderConfig(
            description="x",
            authentication={
                "sensu_host": "http://sensu.example.com:8080",
                "api_key": "k",
                "pull_all_namespaces": True,
            },
        )
        p = SensuProvider(ctx, "s", cfg)
        p.validate_config()
        with patch.object(p, "_api_get", return_value=[]) as mock_get:
            p._get_events()
        called_endpoint = mock_get.call_args[0][0]
        assert called_endpoint == "/api/core/v2/events"


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_api_key_header_set(self, provider):
        headers = provider._get_auth_headers()
        assert headers["Authorization"] == "Key test-api-key-1234"

    def test_bearer_token_used_for_basic_auth(self, ctx, basic_auth_config):
        p = SensuProvider(ctx, "s", basic_auth_config)
        p.validate_config()
        p._access_token = "mock-bearer-token"
        headers = p._get_auth_headers()
        assert headers["Authorization"] == "Bearer mock-bearer-token"

    def test_obtain_access_token_called_once(self, ctx, basic_auth_config):
        p = SensuProvider(ctx, "s", basic_auth_config)
        p.validate_config()

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "tok123"}
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response) as mock_get:
            h1 = p._get_auth_headers()
            h2 = p._get_auth_headers()

        # Should only fetch token once
        assert mock_get.call_count == 1
        assert h1["Authorization"] == "Bearer tok123"
        assert h2["Authorization"] == "Bearer tok123"


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    def test_scopes_valid_when_api_succeeds(self, provider):
        with patch.object(provider, "_get_events", return_value=[]):
            result = provider.validate_scopes()
        assert result["events:get"] is True

    def test_scopes_invalid_when_api_fails(self, provider):
        with patch.object(provider, "_get_events", side_effect=Exception("conn refused")):
            result = provider.validate_scopes()
        assert result["events:get"] == "conn refused"
