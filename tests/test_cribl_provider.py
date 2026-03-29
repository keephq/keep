"""
Comprehensive unit tests for the Cribl provider.

Covers:
- Auth config validation (api_token vs username/password, SSL flag)
- _get_bearer_token (api_token path, login path, error path)
- _headers() helper
- validate_scopes (both scopes pass or return error string on failure)
- _event_to_alert_dto: severity mapping, status mapping, timestamp parsing,
  label extraction, identity fields, edge cases
- _format_alert: single event, list of events, empty list, non-dict items
- _get_alerts: happy path, empty jobs list, bad job status, results fetch failure
- validate_config
- webhook markdown contains expected placeholders

Implementation notes:
- AlertDto stores severity/status as their .value strings (e.g. "critical"),
  not as the enum member itself — comparisons use .value accordingly.
- AlertDto always populates lastReceived with the current time when not
  provided; tests that verify a specific timestamp parse check the actual value.
- _get_alerts calls _get with exact paths; mock side_effect uses 'in' matching.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.cribl_provider.cribl_provider import (
    CriblProvider,
    CriblProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_provider(
    deployment_url: str = "http://cribl.example.com:9000",
    api_token: str = "test-token",
    username: str = None,
    password: str = None,
    verify_ssl: bool = True,
) -> CriblProvider:
    auth: dict = {"deployment_url": deployment_url, "verify_ssl": verify_ssl}
    if api_token:
        auth["api_token"] = api_token
    if username:
        auth["username"] = username
    if password:
        auth["password"] = password

    context_manager = MagicMock(spec=ContextManager)
    context_manager.tenant_id = "test-tenant"

    config = ProviderConfig(authentication=auth)
    provider = CriblProvider(
        context_manager=context_manager,
        provider_id="cribl-test",
        config=config,
    )
    return provider


# ---------------------------------------------------------------------------
# 1. Auth config validation
# ---------------------------------------------------------------------------


class TestCriblProviderAuthConfig:

    def test_api_token_only_is_valid(self):
        cfg = CriblProviderAuthConfig(
            deployment_url="http://localhost:9000",
            api_token="tok",
        )
        assert cfg.api_token == "tok"

    def test_username_password_is_valid(self):
        cfg = CriblProviderAuthConfig(
            deployment_url="http://localhost:9000",
            username="admin",
            password="pass",
        )
        assert cfg.username == "admin"
        assert cfg.password == "pass"

    def test_missing_auth_raises(self):
        with pytest.raises(Exception):
            CriblProviderAuthConfig(deployment_url="http://localhost:9000")

    def test_username_only_raises(self):
        with pytest.raises(Exception):
            CriblProviderAuthConfig(
                deployment_url="http://localhost:9000",
                username="admin",
            )

    def test_verify_ssl_defaults_to_true(self):
        cfg = CriblProviderAuthConfig(
            deployment_url="http://localhost:9000",
            api_token="tok",
        )
        assert cfg.verify_ssl is True

    def test_verify_ssl_can_be_disabled(self):
        cfg = CriblProviderAuthConfig(
            deployment_url="http://localhost:9000",
            api_token="tok",
            verify_ssl=False,
        )
        assert cfg.verify_ssl is False

    def test_invalid_url_raises(self):
        with pytest.raises(Exception):
            CriblProviderAuthConfig(
                deployment_url="not-a-url",
                api_token="tok",
            )


# ---------------------------------------------------------------------------
# 2. validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:

    def test_validate_config_sets_authentication_config(self):
        provider = _make_provider()
        assert isinstance(provider.authentication_config, CriblProviderAuthConfig)
        assert provider.authentication_config.api_token == "test-token"

    def test_validate_config_with_user_pass(self):
        provider = _make_provider(api_token=None, username="admin", password="test-password")
        assert provider.authentication_config.username == "admin"
        assert provider.authentication_config.password == "test-password"


# ---------------------------------------------------------------------------
# 3. _get_bearer_token
# ---------------------------------------------------------------------------


class TestGetBearerToken:

    def test_returns_api_token_directly(self):
        provider = _make_provider(api_token="my-token")
        token = provider._get_bearer_token()
        assert token == "my-token"

    def test_caches_token(self):
        provider = _make_provider(api_token="my-token")
        t1 = provider._get_bearer_token()
        t2 = provider._get_bearer_token()
        assert t1 is t2

    def test_login_with_username_password(self):
        provider = _make_provider(api_token=None, username="u", password="p")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"token": "login-token"}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp) as mock_post:
            token = provider._get_bearer_token()
        assert token == "login-token"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"] == {"username": "u", "password": "p"}

    def test_login_uses_access_token_field(self):
        provider = _make_provider(api_token=None, username="u", password="p")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "at-token"}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            token = provider._get_bearer_token()
        assert token == "at-token"

    def test_login_fails_raises_provider_exception(self):
        import requests as req
        from keep.exceptions.provider_exception import ProviderException

        provider = _make_provider(api_token=None, username="u", password="p")
        with patch("requests.post", side_effect=req.RequestException("timeout")):
            with pytest.raises(ProviderException, match="Failed to authenticate"):
                provider._get_bearer_token()

    def test_login_no_token_in_response_raises(self):
        from keep.exceptions.provider_exception import ProviderException

        provider = _make_provider(api_token=None, username="u", password="p")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "bad creds"}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(ProviderException, match="did not contain a token"):
                provider._get_bearer_token()


# ---------------------------------------------------------------------------
# 4. _headers()
# ---------------------------------------------------------------------------


class TestHeaders:

    def test_headers_contain_bearer_token(self):
        provider = _make_provider(api_token="tok123")
        headers = provider._headers()
        assert headers["Authorization"] == "Bearer tok123"
        assert headers["Accept"] == "application/json"

    def test_headers_content_type(self):
        provider = _make_provider(api_token="tok")
        assert provider._headers()["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# 5. validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:

    def test_both_scopes_pass(self):
        provider = _make_provider()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"items": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            scopes = provider.validate_scopes()
        assert scopes["system:info"] is True
        assert scopes["jobs:read"] is True

    def test_system_info_scope_fails_with_error_message(self):
        from keep.exceptions.provider_exception import ProviderException

        provider = _make_provider()
        with patch.object(provider, "_get", side_effect=ProviderException("conn refused")):
            scopes = provider.validate_scopes()
        assert scopes["system:info"] is not True
        assert "conn refused" in scopes["system:info"]

    def test_jobs_read_scope_fails_with_error_message(self):
        from keep.exceptions.provider_exception import ProviderException

        provider = _make_provider()

        def side_effect(path, *args, **kwargs):
            if path == "/api/v1/system/info":
                return {"version": "4.0"}
            raise ProviderException("no jobs permission")

        with patch.object(provider, "_get", side_effect=side_effect):
            scopes = provider.validate_scopes()
        assert scopes["system:info"] is True
        assert "no jobs permission" in scopes["jobs:read"]


# ---------------------------------------------------------------------------
# 6. _event_to_alert_dto — severity mapping
# ---------------------------------------------------------------------------


class TestEventToAlertDtoSeverity:
    """AlertDto coerces severity to its string value; compare with .value."""

    @pytest.mark.parametrize("raw,expected", [
        ("critical", AlertSeverity.CRITICAL.value),
        ("CRITICAL", AlertSeverity.CRITICAL.value),
        ("crit", AlertSeverity.CRITICAL.value),
        ("emergency", AlertSeverity.CRITICAL.value),
        ("emerg", AlertSeverity.CRITICAL.value),
        ("alert", AlertSeverity.CRITICAL.value),
        ("error", AlertSeverity.HIGH.value),
        ("err", AlertSeverity.HIGH.value),
        ("warning", AlertSeverity.WARNING.value),
        ("warn", AlertSeverity.WARNING.value),
        ("notice", AlertSeverity.INFO.value),
        ("info", AlertSeverity.INFO.value),
        ("informational", AlertSeverity.INFO.value),
        ("debug", AlertSeverity.LOW.value),
        ("0", AlertSeverity.CRITICAL.value),
        ("1", AlertSeverity.CRITICAL.value),
        ("2", AlertSeverity.CRITICAL.value),
        ("3", AlertSeverity.HIGH.value),
        ("4", AlertSeverity.WARNING.value),
        ("5", AlertSeverity.INFO.value),
        ("6", AlertSeverity.INFO.value),
        ("7", AlertSeverity.LOW.value),
        ("fatal", AlertSeverity.CRITICAL.value),
        ("high", AlertSeverity.HIGH.value),
        ("medium", AlertSeverity.WARNING.value),
        ("low", AlertSeverity.LOW.value),
        ("unknown_val", AlertSeverity.INFO.value),  # fallback
        ("", AlertSeverity.INFO.value),
    ])
    def test_severity(self, raw, expected):
        event = {"severity": raw, "title": "test"}
        dto = CriblProvider._event_to_alert_dto(event)
        assert dto.severity == expected

    def test_level_field_used_as_severity(self):
        dto = CriblProvider._event_to_alert_dto({"level": "error"})
        assert dto.severity == AlertSeverity.HIGH.value

    def test_log_level_field_used_as_severity(self):
        dto = CriblProvider._event_to_alert_dto({"log_level": "warn"})
        assert dto.severity == AlertSeverity.WARNING.value

    def test_priority_field_used_as_severity(self):
        dto = CriblProvider._event_to_alert_dto({"priority": "debug"})
        assert dto.severity == AlertSeverity.LOW.value


# ---------------------------------------------------------------------------
# 7. _event_to_alert_dto — status mapping
# ---------------------------------------------------------------------------


class TestEventToAlertDtoStatus:
    """AlertDto coerces status to its string value; compare with .value."""

    @pytest.mark.parametrize("raw,expected", [
        ("firing", AlertStatus.FIRING.value),
        ("active", AlertStatus.FIRING.value),
        ("open", AlertStatus.FIRING.value),
        ("resolved", AlertStatus.RESOLVED.value),
        ("closed", AlertStatus.RESOLVED.value),
        ("ok", AlertStatus.RESOLVED.value),
        ("acknowledged", AlertStatus.ACKNOWLEDGED.value),
        ("ack", AlertStatus.ACKNOWLEDGED.value),
        ("suppressed", AlertStatus.SUPPRESSED.value),
        ("unknown_status", AlertStatus.FIRING.value),  # fallback
    ])
    def test_status(self, raw, expected):
        dto = CriblProvider._event_to_alert_dto({"status": raw})
        assert dto.status == expected

    def test_state_field_used_as_status(self):
        dto = CriblProvider._event_to_alert_dto({"state": "resolved"})
        assert dto.status == AlertStatus.RESOLVED.value


# ---------------------------------------------------------------------------
# 8. _event_to_alert_dto — timestamp parsing
# ---------------------------------------------------------------------------


class TestEventToAlertDtoTimestamp:
    """
    AlertDto always auto-populates lastReceived; we check that a specific
    parsed timestamp lands in the field, and that the 'startedAt' we set
    tracks the parsed value for events that do carry a timestamp.
    """

    def test_unix_epoch_float_sets_started_at(self):
        """A numeric _time should produce a predictable startedAt."""
        ts = 1700000000.5
        dto = CriblProvider._event_to_alert_dto({"_time": ts})
        # startedAt is set from our parsed datetime; lastReceived may differ
        assert dto.startedAt is not None
        assert "2023-11-14" in dto.startedAt  # known date for epoch 1700000000

    def test_unix_epoch_int_sets_started_at(self):
        dto = CriblProvider._event_to_alert_dto({"_time": 1700000000})
        assert dto.startedAt is not None

    def test_iso_string_timestamp(self):
        dto = CriblProvider._event_to_alert_dto({"timestamp": "2024-01-15T10:00:00Z"})
        assert dto.startedAt is not None
        assert "2024-01-15" in dto.startedAt

    def test_iso_string_with_offset(self):
        dto = CriblProvider._event_to_alert_dto({"_time": "2024-06-01T12:00:00+00:00"})
        assert dto.startedAt is not None
        assert "2024-06-01" in dto.startedAt

    def test_bad_timestamp_does_not_crash(self):
        """Provider must never raise on unparseable timestamps."""
        dto = CriblProvider._event_to_alert_dto({"_time": "not-a-date"})
        assert dto is not None
        # startedAt should be None (we passed None to AlertDto)
        assert dto.startedAt is None

    def test_no_timestamp_field_startedAt_none(self):
        """Events with no time field produce startedAt=None."""
        dto = CriblProvider._event_to_alert_dto({"title": "no time"})
        assert dto.startedAt is None

    def test_time_field_alias(self):
        """'time' is also accepted as a timestamp key."""
        dto = CriblProvider._event_to_alert_dto({"time": 1700000000})
        assert dto.startedAt is not None


# ---------------------------------------------------------------------------
# 9. _event_to_alert_dto — name/description/identity
# ---------------------------------------------------------------------------


class TestEventToAlertDtoIdentity:

    def test_title_used_as_name(self):
        dto = CriblProvider._event_to_alert_dto({"title": "Disk Full"})
        assert dto.name == "Disk Full"

    def test_message_fallback_name(self):
        dto = CriblProvider._event_to_alert_dto({"message": "High CPU"})
        assert dto.name == "High CPU"

    def test_raw_truncated_as_name(self):
        raw = "x" * 200
        dto = CriblProvider._event_to_alert_dto({"_raw": raw})
        assert len(dto.name) <= 120

    def test_default_name_when_empty(self):
        dto = CriblProvider._event_to_alert_dto({})
        assert dto.name == "Cribl Event"

    def test_id_field(self):
        dto = CriblProvider._event_to_alert_dto({"_id": "abc-123"})
        assert dto.id == "abc-123"

    def test_event_id_fallback(self):
        dto = CriblProvider._event_to_alert_dto({"event_id": "evt-99"})
        assert dto.id == "evt-99"

    def test_description_field(self):
        dto = CriblProvider._event_to_alert_dto({"description": "disk at 99%"})
        assert dto.description == "disk at 99%"

    def test_raw_used_as_description(self):
        dto = CriblProvider._event_to_alert_dto({"_raw": "raw log line"})
        assert "raw log line" in (dto.description or "")

    def test_host_preserved(self):
        dto = CriblProvider._event_to_alert_dto({"host": "prod-web-01"})
        assert dto.host == "prod-web-01"

    def test_source_always_cribl(self):
        dto = CriblProvider._event_to_alert_dto({"source": "/var/log/app.log"})
        assert "cribl" in dto.source

    def test_cribl_source_preserved(self):
        dto = CriblProvider._event_to_alert_dto({"source": "/var/log/app.log"})
        assert dto.cribl_source == "/var/log/app.log"

    def test_sourcetype_preserved(self):
        dto = CriblProvider._event_to_alert_dto({"sourcetype": "syslog"})
        assert dto.cribl_sourcetype == "syslog"

    def test_non_dict_returns_none(self):
        assert CriblProvider._event_to_alert_dto("not a dict") is None
        assert CriblProvider._event_to_alert_dto(None) is None
        assert CriblProvider._event_to_alert_dto(42) is None

    def test_name_from_alert_name_field(self):
        dto = CriblProvider._event_to_alert_dto({"alert_name": "CPU spike"})
        assert dto.name == "CPU spike"

    def test_name_from_msg_field(self):
        dto = CriblProvider._event_to_alert_dto({"msg": "disk 90%"})
        assert dto.name == "disk 90%"

    def test_guid_as_id_fallback(self):
        dto = CriblProvider._event_to_alert_dto({"guid": "guid-42"})
        assert dto.id == "guid-42"

    def test_cribl_pipe_preserved(self):
        dto = CriblProvider._event_to_alert_dto({"cribl_pipe": "main"})
        assert dto.cribl_pipe == "main"

    def test_cribl_channel_preserved(self):
        dto = CriblProvider._event_to_alert_dto({"cribl_channel": "ch1"})
        assert dto.cribl_channel == "ch1"

    def test_cribl_index_preserved(self):
        dto = CriblProvider._event_to_alert_dto({"index": "prod"})
        assert dto.cribl_index == "prod"

    def test_description_from_detail_field(self):
        dto = CriblProvider._event_to_alert_dto({"detail": "detailed description"})
        assert dto.description == "detailed description"

    def test_description_from_summary_field(self):
        dto = CriblProvider._event_to_alert_dto({"summary": "brief summary"})
        assert dto.description == "brief summary"


# ---------------------------------------------------------------------------
# 10. _event_to_alert_dto — label extraction
# ---------------------------------------------------------------------------


class TestEventToAlertDtoLabels:

    def test_labels_dict(self):
        dto = CriblProvider._event_to_alert_dto({"labels": {"env": "prod", "team": "infra"}})
        assert dto.labels["env"] == "prod"
        assert dto.labels["team"] == "infra"

    def test_tags_list_of_strings(self):
        dto = CriblProvider._event_to_alert_dto({"tags": ["k8s", "production"]})
        assert "k8s" in dto.labels
        assert "production" in dto.labels

    def test_tags_list_of_key_value_dicts(self):
        dto = CriblProvider._event_to_alert_dto(
            {"tags": [{"key": "dc", "value": "us-east"}, {"key": "env", "value": "prod"}]}
        )
        assert dto.labels["dc"] == "us-east"
        assert dto.labels["env"] == "prod"

    def test_metadata_dict(self):
        dto = CriblProvider._event_to_alert_dto({"metadata": {"region": "eu-west-1"}})
        assert dto.labels["region"] == "eu-west-1"

    def test_source_job_labels_added(self):
        job = {"id": "job-1", "type": "search", "query": "error", "workerCount": 4}
        dto = CriblProvider._event_to_alert_dto({"_id": "e1"}, source_job=job)
        assert dto.labels.get("cribl_job_type") == "search"
        assert dto.labels.get("cribl_job_query") == "error"
        assert dto.labels.get("cribl_job_workerCount") == "4"

    def test_fields_dict_merged_into_labels(self):
        dto = CriblProvider._event_to_alert_dto({"fields": {"dc": "us-west", "tier": "web"}})
        assert dto.labels["dc"] == "us-west"
        assert dto.labels["tier"] == "web"

    def test_tags_list_with_name_field(self):
        dto = CriblProvider._event_to_alert_dto(
            {"tags": [{"name": "sev", "value": "high"}]}
        )
        assert dto.labels.get("sev") == "high"

    def test_empty_labels_dict(self):
        dto = CriblProvider._event_to_alert_dto({"labels": {}})
        assert dto.labels == {}

    def test_labels_values_coerced_to_str(self):
        dto = CriblProvider._event_to_alert_dto({"labels": {"count": 42, "flag": True}})
        assert dto.labels["count"] == "42"
        assert dto.labels["flag"] == "True"


# ---------------------------------------------------------------------------
# 11. _format_alert (static, webhook path)
# ---------------------------------------------------------------------------


class TestFormatAlert:

    def test_single_event_returns_single_dto(self):
        result = CriblProvider._format_alert({"title": "Test", "severity": "critical"})
        assert hasattr(result, "name")
        assert result.name == "Test"
        assert result.severity == AlertSeverity.CRITICAL.value

    def test_list_of_events_returns_list_of_dtos(self):
        events = [
            {"title": "Event A", "severity": "error"},
            {"title": "Event B", "severity": "info"},
        ]
        result = CriblProvider._format_alert(events)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].name == "Event A"
        assert result[1].name == "Event B"

    def test_empty_list_returns_empty_list(self):
        result = CriblProvider._format_alert([])
        assert result == []

    def test_list_with_non_dict_skipped(self):
        result = CriblProvider._format_alert(["not-a-dict", None])
        assert result == []

    def test_list_mixed_valid_invalid(self):
        result = CriblProvider._format_alert([{"title": "Good"}, "bad", None])
        assert len(result) == 1
        assert result[0].name == "Good"

    def test_empty_dict_returns_fallback_dto(self):
        result = CriblProvider._format_alert({})
        assert result.name == "Cribl Event"

    def test_severity_preserved_through_format_alert(self):
        result = CriblProvider._format_alert({"severity": "warning"})
        assert result.severity == AlertSeverity.WARNING.value

    def test_status_preserved_through_format_alert(self):
        result = CriblProvider._format_alert({"status": "resolved"})
        assert result.status == AlertStatus.RESOLVED.value

    def test_list_severities_correct(self):
        events = [{"severity": "critical"}, {"severity": "low"}]
        result = CriblProvider._format_alert(events)
        assert result[0].severity == AlertSeverity.CRITICAL.value
        assert result[1].severity == AlertSeverity.LOW.value


# ---------------------------------------------------------------------------
# 12. _get_alerts (pull mode)
# ---------------------------------------------------------------------------


class TestGetAlerts:

    def test_no_jobs_returns_empty(self):
        provider = _make_provider()
        with patch.object(provider, "_get", return_value={"items": []}):
            alerts = provider._get_alerts()
        assert alerts == []

    def test_jobs_list_direct_array_empty(self):
        """Some Cribl versions return the array directly (no items key)."""
        provider = _make_provider()
        with patch.object(provider, "_get", return_value=[]):
            alerts = provider._get_alerts()
        assert alerts == []

    def test_completed_job_with_results(self):
        provider = _make_provider()
        jobs_response = {
            "items": [{"id": "j1", "status": "completed"}]
        }
        results_response = {
            "results": [
                {"title": "Alert 1", "severity": "error", "_time": 1700000000},
                {"title": "Alert 2", "severity": "warn"},
            ]
        }

        def mock_get(path, params=None):
            if "results" in path:
                return results_response
            return jobs_response

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()

        assert len(alerts) == 2
        names = {a.name for a in alerts}
        assert "Alert 1" in names
        assert "Alert 2" in names

    def test_alert_severity_from_pull(self):
        provider = _make_provider()

        def mock_get(path, params=None):
            if "results" in path:
                return {"results": [{"title": "E", "severity": "error"}]}
            return {"items": [{"id": "j1", "status": "completed"}]}

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()

        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH.value

    def test_running_job_included(self):
        provider = _make_provider()
        jobs_response = {"items": [{"id": "j2", "status": "running"}]}
        results_response = {"results": [{"title": "Live Event"}]}

        def mock_get(path, params=None):
            if "results" in path:
                return results_response
            return jobs_response

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()
        assert len(alerts) == 1

    def test_done_status_job_included(self):
        provider = _make_provider()
        jobs_response = {"items": [{"id": "j3", "status": "done"}]}
        results_response = {"results": [{"title": "Done Event"}]}

        def mock_get(path, params=None):
            if "results" in path:
                return results_response
            return jobs_response

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()
        assert len(alerts) == 1

    def test_non_running_job_skipped(self):
        provider = _make_provider()
        jobs_response = {"items": [{"id": "j4", "status": "failed"}]}

        with patch.object(provider, "_get", return_value=jobs_response):
            alerts = provider._get_alerts()
        assert len(alerts) == 0

    def test_pending_job_skipped(self):
        provider = _make_provider()
        jobs_response = {"items": [{"id": "j5", "status": "pending"}]}

        with patch.object(provider, "_get", return_value=jobs_response):
            alerts = provider._get_alerts()
        assert len(alerts) == 0

    def test_job_without_id_skipped(self):
        provider = _make_provider()
        jobs_response = {"items": [{"status": "completed"}]}  # no id

        with patch.object(provider, "_get", return_value=jobs_response):
            alerts = provider._get_alerts()
        assert len(alerts) == 0

    def test_results_fetch_failure_returns_empty_list(self):
        from keep.exceptions.provider_exception import ProviderException

        provider = _make_provider()
        jobs_response = {"items": [{"id": "jX", "status": "completed"}]}

        def mock_get(path, params=None):
            if "results" in path:
                raise ProviderException("results unavailable")
            return jobs_response

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()
        assert alerts == []

    def test_overall_jobs_failure_returns_empty(self):
        from keep.exceptions.provider_exception import ProviderException

        provider = _make_provider()
        with patch.object(provider, "_get", side_effect=ProviderException("no access")):
            alerts = provider._get_alerts()
        assert alerts == []

    def test_results_in_items_key(self):
        provider = _make_provider()
        jobs_response = {"items": [{"id": "j6", "status": "done"}]}
        results_response = {"items": [{"title": "Via items key"}]}

        def mock_get(path, params=None):
            if "results" in path:
                return results_response
            return jobs_response

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()
        assert len(alerts) == 1
        assert alerts[0].name == "Via items key"

    def test_multiple_jobs_combined(self):
        provider = _make_provider()
        jobs_response = {
            "items": [
                {"id": "ja", "status": "completed"},
                {"id": "jb", "status": "completed"},
            ]
        }

        def mock_get(path, params=None):
            if "results" in path:
                return {"results": [{"title": "Event from " + path.split("/")[4]}]}
            return jobs_response

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()
        assert len(alerts) == 2

    def test_job_labels_added_to_alerts(self):
        provider = _make_provider()

        def mock_get(path, params=None):
            if "results" in path:
                return {"results": [{"title": "E"}]}
            return {"items": [{"id": "j1", "status": "completed", "type": "search"}]}

        with patch.object(provider, "_get", side_effect=mock_get):
            alerts = provider._get_alerts()
        assert len(alerts) == 1
        assert alerts[0].labels.get("cribl_job_type") == "search"


# ---------------------------------------------------------------------------
# 13. Provider metadata
# ---------------------------------------------------------------------------


class TestProviderMetadata:

    def test_display_name(self):
        assert CriblProvider.PROVIDER_DISPLAY_NAME == "Cribl"

    def test_provider_category_monitoring(self):
        assert "Monitoring" in CriblProvider.PROVIDER_CATEGORY

    def test_provider_category_developer_tools(self):
        assert "Developer Tools" in CriblProvider.PROVIDER_CATEGORY

    def test_provider_tags_alert(self):
        assert "alert" in CriblProvider.PROVIDER_TAGS

    def test_provider_tags_data(self):
        assert "data" in CriblProvider.PROVIDER_TAGS

    def test_webhook_markdown_has_url_placeholder(self):
        assert "{keep_webhook_api_url}" in CriblProvider.webhook_markdown

    def test_webhook_markdown_has_api_key_placeholder(self):
        assert "{api_key}" in CriblProvider.webhook_markdown

    def test_webhook_markdown_mentions_http_destination(self):
        assert "HTTP" in CriblProvider.webhook_markdown

    def test_fingerprint_fields_defined(self):
        assert len(CriblProvider.FINGERPRINT_FIELDS) > 0

    def test_fingerprint_includes_host(self):
        assert "host" in CriblProvider.FINGERPRINT_FIELDS

    def test_provider_scopes_defined(self):
        assert len(CriblProvider.PROVIDER_SCOPES) >= 2

    def test_system_info_scope_mandatory(self):
        scope_names = [s.name for s in CriblProvider.PROVIDER_SCOPES]
        assert "system:info" in scope_names

    def test_jobs_read_scope_present(self):
        scope_names = [s.name for s in CriblProvider.PROVIDER_SCOPES]
        assert "jobs:read" in scope_names

    def test_dispose_does_not_raise(self):
        provider = _make_provider()
        provider.dispose()

    def test_severities_map_covers_syslog_numerics(self):
        for n in ["0", "1", "2", "3", "4", "5", "6", "7"]:
            assert n in CriblProvider.SEVERITIES_MAP

    def test_status_map_covers_key_states(self):
        for state in ("firing", "resolved", "acknowledged"):
            assert state in CriblProvider.STATUS_MAP
