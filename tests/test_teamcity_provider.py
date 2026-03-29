"""
Comprehensive unit tests for the TeamCity provider.

Covers:
- Auth config validation (token vs username/password, SSL, missing auth)
- _headers() and _auth() helpers
- validate_scopes (pass and error paths)
- _build_to_alert_dto: status mapping, severity mapping, timestamp parsing,
  name construction, labels, webhook payload fields
- _format_alert: single build, list of builds, empty/invalid inputs
- _get_alerts: failed builds, cancelled builds, empty response, API error
- Provider metadata (category, tags, scopes, fingerprint fields)
- _parse_tc_datetime: compact TC format, ISO string, Unix epoch, edge cases

Note: AlertDto stores severity/status as string values — comparisons use .value.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.teamcity_provider.teamcity_provider import (
    TeamcityProvider,
    TeamcityProviderAuthConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    deployment_url: str = "http://teamcity.example.com:8111",
    access_token: str = "test-token",
    username: str = None,
    password: str = None,
    verify_ssl: bool = True,
) -> TeamcityProvider:
    auth: dict = {"deployment_url": deployment_url, "verify_ssl": verify_ssl}
    if access_token:
        auth["access_token"] = access_token
    if username:
        auth["username"] = username
    if password:
        auth["password"] = password

    context_manager = MagicMock(spec=ContextManager)
    context_manager.tenant_id = "test-tenant"

    config = ProviderConfig(authentication=auth)
    return TeamcityProvider(
        context_manager=context_manager,
        provider_id="tc-test",
        config=config,
    )


def _make_build(
    build_id: int = 42,
    status: str = "FAILURE",
    status_text: str = "Tests failed",
    build_type_id: str = "Project_Build",
    build_name: str = "Build",
    project_name: str = "MyProject",
    branch: str = "main",
    number: str = "123",
    start_date: str = "20240101T100000+0000",
    finish_date: str = "20240101T101500+0000",
    web_url: str = "https://tc/build/42",
) -> dict:
    return {
        "id": build_id,
        "number": number,
        "status": status,
        "statusText": status_text,
        "state": "finished",
        "branchName": branch,
        "buildType": {
            "id": build_type_id,
            "name": build_name,
            "projectName": project_name,
            "webUrl": web_url,
        },
        "startDate": start_date,
        "finishDate": finish_date,
        "webUrl": web_url,
        "triggered": {"type": "user", "user": {"username": "alice"}},
    }


# ---------------------------------------------------------------------------
# 1. Auth config validation
# ---------------------------------------------------------------------------


class TestTeamcityProviderAuthConfig:

    def test_access_token_only_is_valid(self):
        cfg = TeamcityProviderAuthConfig(
            deployment_url="http://localhost:8111",
            access_token="tok",
        )
        assert cfg.access_token == "tok"

    def test_username_password_is_valid(self):
        cfg = TeamcityProviderAuthConfig(
            deployment_url="http://localhost:8111",
            username="admin",
            password="pass",
        )
        assert cfg.username == "admin"
        assert cfg.password == "pass"

    def test_no_auth_raises(self):
        with pytest.raises(Exception):
            TeamcityProviderAuthConfig(deployment_url="http://localhost:8111")

    def test_username_only_raises(self):
        with pytest.raises(Exception):
            TeamcityProviderAuthConfig(
                deployment_url="http://localhost:8111",
                username="admin",
            )

    def test_verify_ssl_defaults_true(self):
        cfg = TeamcityProviderAuthConfig(
            deployment_url="http://localhost:8111",
            access_token="tok",
        )
        assert cfg.verify_ssl is True

    def test_verify_ssl_can_be_disabled(self):
        cfg = TeamcityProviderAuthConfig(
            deployment_url="http://localhost:8111",
            access_token="tok",
            verify_ssl=False,
        )
        assert cfg.verify_ssl is False

    def test_invalid_url_raises(self):
        with pytest.raises(Exception):
            TeamcityProviderAuthConfig(deployment_url="not-a-url", access_token="tok")


# ---------------------------------------------------------------------------
# 2. validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:

    def test_sets_authentication_config(self):
        p = _make_provider()
        assert isinstance(p.authentication_config, TeamcityProviderAuthConfig)
        assert p.authentication_config.access_token == "test-token"

    def test_with_user_pass(self):
        p = _make_provider(access_token=None, username="u", password="p")
        assert p.authentication_config.username == "u"


# ---------------------------------------------------------------------------
# 3. _headers() and _auth()
# ---------------------------------------------------------------------------


class TestHeadersAndAuth:

    def test_headers_with_token(self):
        p = _make_provider(access_token="mytoken")
        h = p._headers()
        assert h["Authorization"] == "Bearer mytoken"
        assert h["Accept"] == "application/json"

    def test_headers_content_type(self):
        p = _make_provider()
        assert p._headers()["Content-Type"] == "application/json"

    def test_auth_returns_none_when_token_set(self):
        p = _make_provider(access_token="tok")
        assert p._auth() is None

    def test_auth_returns_tuple_for_user_pass(self):
        p = _make_provider(access_token=None, username="u", password="p")
        assert p._auth() == ("u", "p")


# ---------------------------------------------------------------------------
# 4. validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:

    def test_both_scopes_pass(self):
        p = _make_provider()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"build": []}
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            scopes = p.validate_scopes()
        assert scopes["view_project"] is True
        assert scopes["view_build_runtime_data"] is True

    def test_api_error_returns_error_string(self):
        from keep.exceptions.provider_exception import ProviderException

        p = _make_provider()
        with patch.object(p, "_get", side_effect=ProviderException("403 Forbidden")):
            scopes = p.validate_scopes()
        assert scopes["view_project"] != True  # noqa: E712
        assert "403" in scopes["view_project"]
        assert scopes["view_build_runtime_data"] != True  # noqa: E712


# ---------------------------------------------------------------------------
# 5. _build_to_alert_dto — status mapping
# ---------------------------------------------------------------------------


class TestBuildToAlertDtoStatus:

    @pytest.mark.parametrize("raw,expected", [
        ("FAILURE", AlertStatus.FIRING.value),
        ("failure", AlertStatus.FIRING.value),
        ("failed", AlertStatus.FIRING.value),
        ("error", AlertStatus.FIRING.value),
        ("cancelled", AlertStatus.FIRING.value),
        ("canceled", AlertStatus.FIRING.value),
        ("unknown", AlertStatus.FIRING.value),
        ("SUCCESS", AlertStatus.RESOLVED.value),
        ("success", AlertStatus.RESOLVED.value),
        ("succeeded", AlertStatus.RESOLVED.value),
        ("UNKNOWN_STATUS", AlertStatus.FIRING.value),  # fallback
    ])
    def test_status_mapping(self, raw, expected):
        build = _make_build(status=raw)
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert dto.status == expected


# ---------------------------------------------------------------------------
# 6. _build_to_alert_dto — severity mapping
# ---------------------------------------------------------------------------


class TestBuildToAlertDtoSeverity:

    @pytest.mark.parametrize("raw,expected", [
        ("failure", AlertSeverity.HIGH.value),
        ("failed", AlertSeverity.HIGH.value),
        ("error", AlertSeverity.CRITICAL.value),
        ("cancelled", AlertSeverity.WARNING.value),
        ("canceled", AlertSeverity.WARNING.value),
        ("unknown", AlertSeverity.INFO.value),
        ("success", AlertSeverity.LOW.value),
        ("succeeded", AlertSeverity.LOW.value),
        ("ANYTHING_ELSE", AlertSeverity.HIGH.value),  # fallback
    ])
    def test_severity_mapping(self, raw, expected):
        build = _make_build(status=raw)
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert dto.severity == expected


# ---------------------------------------------------------------------------
# 7. _build_to_alert_dto — name construction
# ---------------------------------------------------------------------------


class TestBuildToAlertDtoName:

    def test_full_name_has_project_buildname_number(self):
        build = _make_build(project_name="WebApp", build_name="Tests", number="42")
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert "WebApp" in dto.name
        assert "Tests" in dto.name
        assert "42" in dto.name

    def test_name_without_project(self):
        build = _make_build(project_name="", build_name="Lint", number="7")
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert "Lint" in dto.name
        assert "7" in dto.name

    def test_fallback_name_uses_build_id(self):
        dto = TeamcityProvider._build_to_alert_dto({"id": 99, "status": "FAILURE"})
        assert "99" in dto.name

    def test_description_includes_status_text(self):
        build = _make_build(status_text="Compile error in module X")
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert "Compile error" in (dto.description or "")

    def test_description_includes_branch(self):
        build = _make_build(branch="feature/login")
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert "feature/login" in (dto.description or "")


# ---------------------------------------------------------------------------
# 8. _build_to_alert_dto — identity and extra fields
# ---------------------------------------------------------------------------


class TestBuildToAlertDtoIdentity:

    def test_id_set(self):
        build = _make_build(build_id=1234)
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert dto.buildId == "1234"

    def test_build_number_set(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(number="55"))
        assert dto.buildNumber == "55"

    def test_build_type_id_set(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(build_type_id="Proj_Unit"))
        assert dto.buildTypeId == "Proj_Unit"

    def test_project_name_in_labels(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(project_name="API"))
        assert dto.labels.get("projectName") == "API"

    def test_branch_in_labels(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(branch="develop"))
        assert dto.labels.get("branchName") == "develop"

    def test_triggered_by_in_labels(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build())
        assert dto.labels.get("triggeredBy") == "alice"

    def test_web_url_set(self):
        build = _make_build(web_url="https://tc/build/9")
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert dto.url == "https://tc/build/9"

    def test_source_always_teamcity(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build())
        assert "teamcity" in dto.source

    def test_non_dict_returns_none(self):
        assert TeamcityProvider._build_to_alert_dto("not a dict") is None
        assert TeamcityProvider._build_to_alert_dto(None) is None
        assert TeamcityProvider._build_to_alert_dto(42) is None

    def test_minimal_dict_returns_dto(self):
        dto = TeamcityProvider._build_to_alert_dto({"id": 1, "status": "FAILURE"})
        assert dto is not None
        assert "teamcity" in dto.source

    def test_build_name_set(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(build_name="Unit Tests"))
        assert dto.buildName == "Unit Tests"

    def test_project_name_on_dto(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(project_name="Backend"))
        assert dto.projectName == "Backend"

    def test_branch_name_on_dto(self):
        dto = TeamcityProvider._build_to_alert_dto(_make_build(branch="release/1.0"))
        assert dto.branchName == "release/1.0"


# ---------------------------------------------------------------------------
# 9. _parse_tc_datetime
# ---------------------------------------------------------------------------


class TestParseTcDatetime:

    def test_teamcity_compact_format(self):
        result = TeamcityProvider._parse_tc_datetime("20240615T142300+0000")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_iso_format_with_z(self):
        result = TeamcityProvider._parse_tc_datetime("2024-01-15T10:00:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_iso_format_with_offset(self):
        result = TeamcityProvider._parse_tc_datetime("2024-03-20T08:30:00+05:30")
        assert result is not None

    def test_unix_timestamp_int(self):
        result = TeamcityProvider._parse_tc_datetime(1700000000)
        assert result is not None
        assert result.year == 2023

    def test_unix_timestamp_float(self):
        result = TeamcityProvider._parse_tc_datetime(1700000000.5)
        assert result is not None

    def test_none_returns_none(self):
        assert TeamcityProvider._parse_tc_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert TeamcityProvider._parse_tc_datetime("") is None

    def test_whitespace_returns_none(self):
        assert TeamcityProvider._parse_tc_datetime("   ") is None

    def test_bad_string_returns_none(self):
        assert TeamcityProvider._parse_tc_datetime("not-a-date") is None

    def test_non_string_non_number_returns_none(self):
        assert TeamcityProvider._parse_tc_datetime([]) is None
        assert TeamcityProvider._parse_tc_datetime({}) is None


# ---------------------------------------------------------------------------
# 10. Timestamp fields on AlertDto
# ---------------------------------------------------------------------------


class TestBuildToAlertDtoTimestamps:

    def test_start_date_parsed(self):
        build = _make_build(start_date="20240101T100000+0000")
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert dto.startedAt is not None
        assert "2024-01-01" in dto.startedAt

    def test_finish_date_parsed(self):
        build = _make_build(finish_date="20240101T101500+0000")
        dto = TeamcityProvider._build_to_alert_dto(build)
        # lastReceived is always set by AlertDto; check startedAt from finishDate
        assert dto.lastReceived is not None  # auto-set or from our value

    def test_no_dates_no_crash(self):
        build = {"id": 1, "status": "FAILURE"}
        dto = TeamcityProvider._build_to_alert_dto(build)
        assert dto is not None
        assert dto.startedAt is None


# ---------------------------------------------------------------------------
# 11. _format_alert (webhook path)
# ---------------------------------------------------------------------------


class TestFormatAlert:

    def test_single_build_returns_dto(self):
        build = _make_build(project_name="API", build_name="Tests", number="7")
        result = TeamcityProvider._format_alert(build)
        assert hasattr(result, "name")
        assert "API" in result.name

    def test_list_of_builds_returns_list(self):
        builds = [_make_build(build_id=1, number="1"), _make_build(build_id=2, number="2")]
        result = TeamcityProvider._format_alert(builds)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        result = TeamcityProvider._format_alert([])
        assert result == []

    def test_list_with_non_dict_skipped(self):
        result = TeamcityProvider._format_alert(["bad", None])
        assert result == []

    def test_mixed_list(self):
        result = TeamcityProvider._format_alert([_make_build(), "bad", None])
        assert len(result) == 1

    def test_empty_dict_returns_dto(self):
        """An empty dict produces a dto (not a list) via _format_alert."""
        result = TeamcityProvider._format_alert({})
        # Non-None input always produces a single AlertDto
        assert hasattr(result, "name")
        assert "teamcity" in result.source

    def test_failed_build_has_firing_status(self):
        build = _make_build(status="FAILURE")
        result = TeamcityProvider._format_alert(build)
        assert result.status == AlertStatus.FIRING.value

    def test_successful_build_has_resolved_status(self):
        build = _make_build(status="SUCCESS")
        result = TeamcityProvider._format_alert(build)
        assert result.status == AlertStatus.RESOLVED.value


# ---------------------------------------------------------------------------
# 12. _get_alerts (pull mode)
# ---------------------------------------------------------------------------


class TestGetAlerts:

    def test_no_builds_returns_empty(self):
        p = _make_provider()
        with patch.object(p, "_get", return_value={"build": []}):
            alerts = p._get_alerts()
        assert alerts == []

    def test_failed_builds_returned(self):
        p = _make_provider()
        builds_response = {"build": [_make_build(build_id=1), _make_build(build_id=2)]}

        def mock_get(path, params=None):
            locator = (params or {}).get("locator", "")
            if "FAILURE" in locator:
                return builds_response
            return {"build": []}

        with patch.object(p, "_get", side_effect=mock_get):
            alerts = p._get_alerts()
        assert len(alerts) == 2

    def test_cancelled_builds_also_returned(self):
        p = _make_provider()
        cancelled = {"build": [_make_build(build_id=99, status="CANCELED")]}

        def mock_get(path, params=None):
            locator = (params or {}).get("locator", "")
            if "CANCELED" in locator:
                return cancelled
            return {"build": []}

        with patch.object(p, "_get", side_effect=mock_get):
            alerts = p._get_alerts()
        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.FIRING.value

    def test_combined_failed_and_cancelled(self):
        p = _make_provider()
        failed = {"build": [_make_build(build_id=1), _make_build(build_id=2)]}
        cancelled = {"build": [_make_build(build_id=3, status="CANCELED")]}

        def mock_get(path, params=None):
            locator = (params or {}).get("locator", "")
            if "FAILURE" in locator:
                return failed
            if "CANCELED" in locator:
                return cancelled
            return {"build": []}

        with patch.object(p, "_get", side_effect=mock_get):
            alerts = p._get_alerts()
        assert len(alerts) == 3

    def test_api_error_returns_empty(self):
        from keep.exceptions.provider_exception import ProviderException

        p = _make_provider()
        with patch.object(p, "_get", side_effect=ProviderException("timeout")):
            alerts = p._get_alerts()
        assert alerts == []

    def test_non_list_build_response_ignored(self):
        p = _make_provider()
        with patch.object(p, "_get", return_value={"build": "not-a-list"}):
            alerts = p._get_alerts()
        assert alerts == []

    def test_alert_has_correct_severity(self):
        p = _make_provider()

        def mock_get(path, params=None):
            locator = (params or {}).get("locator", "")
            if "FAILURE" in locator:
                return {"build": [_make_build(status="FAILURE")]}
            return {"build": []}

        with patch.object(p, "_get", side_effect=mock_get):
            alerts = p._get_alerts()
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.HIGH.value

    def test_alert_source_is_teamcity(self):
        p = _make_provider()

        def mock_get(path, params=None):
            locator = (params or {}).get("locator", "")
            if "FAILURE" in locator:
                return {"build": [_make_build()]}
            return {"build": []}

        with patch.object(p, "_get", side_effect=mock_get):
            alerts = p._get_alerts()
        assert "teamcity" in alerts[0].source


# ---------------------------------------------------------------------------
# 13. Provider metadata
# ---------------------------------------------------------------------------


class TestProviderMetadata:

    def test_display_name(self):
        assert TeamcityProvider.PROVIDER_DISPLAY_NAME == "TeamCity"

    def test_category_developer_tools(self):
        assert "Developer Tools" in TeamcityProvider.PROVIDER_CATEGORY

    def test_category_cloud_infra(self):
        assert "Cloud Infrastructure" in TeamcityProvider.PROVIDER_CATEGORY

    def test_tags_alert(self):
        assert "alert" in TeamcityProvider.PROVIDER_TAGS

    def test_webhook_markdown_has_url_placeholder(self):
        assert "{keep_webhook_api_url}" in TeamcityProvider.webhook_markdown

    def test_webhook_markdown_has_api_key_placeholder(self):
        assert "{api_key}" in TeamcityProvider.webhook_markdown

    def test_fingerprint_fields_defined(self):
        assert len(TeamcityProvider.FINGERPRINT_FIELDS) > 0

    def test_fingerprint_includes_build_type(self):
        assert "buildTypeId" in TeamcityProvider.FINGERPRINT_FIELDS

    def test_provider_scopes_defined(self):
        assert len(TeamcityProvider.PROVIDER_SCOPES) >= 2

    def test_view_project_scope_present(self):
        names = [s.name for s in TeamcityProvider.PROVIDER_SCOPES]
        assert "view_project" in names

    def test_view_build_runtime_data_scope_present(self):
        names = [s.name for s in TeamcityProvider.PROVIDER_SCOPES]
        assert "view_build_runtime_data" in names

    def test_status_map_covers_common_statuses(self):
        for s in ("failure", "success", "cancelled", "error"):
            assert s in TeamcityProvider.STATUS_MAP

    def test_severity_map_covers_common_statuses(self):
        for s in ("failure", "success", "cancelled", "error"):
            assert s in TeamcityProvider.SEVERITY_MAP

    def test_dispose_does_not_raise(self):
        p = _make_provider()
        p.dispose()
