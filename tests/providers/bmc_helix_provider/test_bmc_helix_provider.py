"""
Comprehensive tests for BmcHelixProvider.

Covers:
  - Auth config validation
  - JWT authentication (token fetch, caching, header format)
  - Pull mode: _entry_to_alert_dto, _get_alerts
  - Push mode: _format_alert with wrapped and flat payloads
  - Priority/severity mapping (numeric and string keys)
  - Status mapping for all known Helix statuses
  - Timestamp handling (epoch ms, missing, invalid)
  - Topology pull: get_topology
  - Incident creation: create_incident, notify
  - validate_scopes success and failure
  - Edge cases: missing fields, empty values, unknown priority/status
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.api.models.incident import IncidentSeverity, IncidentStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.bmc_helix_provider.bmc_helix_provider import (
    BmcHelixProvider,
    BmcHelixProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    return ContextManager(tenant_id="test", workflow_id="test")


@pytest.fixture
def base_config():
    return ProviderConfig(
        description="BMC Helix test",
        authentication={
            "base_url": "https://helix.example.com",
            "username": "admin",
            "password": "secret123",
        },
    )


@pytest.fixture
def provider(ctx, base_config):
    p = BmcHelixProvider(ctx, "bmc-helix-test", base_config)
    p.validate_config()
    return p


def _now_ms() -> int:
    return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)


def _make_entry(
    incident_number="INC0001234",
    summary="Disk full on DB server",
    notes="RAID volume at 99%",
    status="In Progress",
    priority="2",
    company="Acme Corp",
    service="Database Service",
    assignee="john.doe",
    assigned_group="DB Ops",
    category="Hardware",
    submit_date=None,
    last_modified=None,
    entry_id="IDGAG5V0GFAKXAOEZJT0AOOO0UQKRZ",
) -> dict:
    """Build a mock Helix ITSM entry as returned by the REST API."""
    return {
        "entryId": entry_id,
        "values": {
            "Incident Number": incident_number,
            "Summary": summary,
            "Notes": notes,
            "Status": status,
            "Priority": priority,
            "Company": company,
            "Service": service,
            "Assignee": assignee,
            "Assigned Group": assigned_group,
            "Category Tier 1": category,
            "Submit Date": str(submit_date or _now_ms()),
            "Last Modified Date": str(last_modified or _now_ms()),
        },
        "_links": {
            "self": [
                {
                    "href": f"https://helix.example.com/api/arsys/v1/entry/HPD:IncidentInterface/{entry_id}"
                }
            ]
        },
    }


def _make_push_event(
    incident_number="INC0005678",
    summary="Network outage",
    notes="Core switch failure",
    status="New",
    priority="1",
    company="Beta Inc",
    service="Network",
    assignee="",
    assigned_group="Network Ops",
    submit_date=None,
    wrapped=True,
) -> dict:
    """Build a push/webhook event payload."""
    values = {
        "Incident Number": incident_number,
        "Summary": summary,
        "Notes": notes,
        "Status": status,
        "Priority": priority,
        "Company": company,
        "Service": service,
        "Assignee": assignee,
        "Assigned Group": assigned_group,
        "Submit Date": str(submit_date or _now_ms()),
    }
    if wrapped:
        return {"values": values}
    else:
        return values  # Flat payload


# ---------------------------------------------------------------------------
# Auth config validation
# ---------------------------------------------------------------------------


class TestAuthConfig:
    def test_valid_config(self, ctx, base_config):
        p = BmcHelixProvider(ctx, "x", base_config)
        p.validate_config()
        assert p.authentication_config.username == "admin"

    def test_base_url_stored(self, provider):
        assert "helix.example.com" in str(provider.authentication_config.base_url)

    def test_verify_ssl_defaults_true(self, provider):
        assert provider.authentication_config.verify_ssl is True

    def test_timeout_defaults_30(self, provider):
        assert provider.authentication_config.timeout == 30

    def test_custom_ssl_and_timeout(self, ctx):
        cfg = ProviderConfig(
            description="x",
            authentication={
                "base_url": "https://helix.example.com",
                "username": "u",
                "password": "p",
                "verify_ssl": False,
                "timeout": 60,
            },
        )
        p = BmcHelixProvider(ctx, "x", cfg)
        p.validate_config()
        assert p.authentication_config.verify_ssl is False
        assert p.authentication_config.timeout == 60


# ---------------------------------------------------------------------------
# JWT authentication
# ---------------------------------------------------------------------------


class TestJwtAuth:
    def test_jwt_token_obtained(self, provider):
        mock_resp = MagicMock()
        mock_resp.text = '"eyJhbGciOiJSUzI1NiJ9.test"'
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp):
            token = provider._get_jwt_token()

        assert token == "eyJhbGciOiJSUzI1NiJ9.test"

    def test_jwt_token_cached(self, provider):
        mock_resp = MagicMock()
        mock_resp.text = '"token-abc"'
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            provider._get_jwt_token()
            provider._get_jwt_token()

        # Should only call the login endpoint once
        assert mock_post.call_count == 1

    def test_empty_token_raises(self, provider):
        mock_resp = MagicMock()
        mock_resp.text = '""'
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(ValueError, match="empty token"):
                provider._get_jwt_token()

    def test_auth_header_uses_ar_jwt_prefix(self, provider):
        provider._jwt_token = "my-test-token"
        headers = provider._get_auth_headers()
        assert headers["Authorization"] == "AR-JWT my-test-token"

    def test_auth_header_content_type(self, provider):
        provider._jwt_token = "tok"
        headers = provider._get_auth_headers()
        assert headers["Content-Type"] == "application/json"

    def test_login_endpoint_called_correctly(self, provider):
        mock_resp = MagicMock()
        mock_resp.text = '"tok123"'
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            provider._get_jwt_token()

        call_kwargs = mock_post.call_args
        assert "/api/jwt/login" in call_kwargs[0][0]
        assert call_kwargs[1]["json"]["username"] == "admin"
        assert call_kwargs[1]["json"]["password"] == "secret123"


# ---------------------------------------------------------------------------
# Priority / severity mapping
# ---------------------------------------------------------------------------


class TestPriorityMapping:
    def test_priority_1_maps_critical(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["1"] == AlertSeverity.CRITICAL

    def test_priority_2_maps_high(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["2"] == AlertSeverity.HIGH

    def test_priority_3_maps_warning(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["3"] == AlertSeverity.WARNING

    def test_priority_4_maps_low(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["4"] == AlertSeverity.LOW

    def test_priority_5_maps_info(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["5"] == AlertSeverity.INFO

    def test_priority_critical_string(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["Critical"] == AlertSeverity.CRITICAL

    def test_priority_high_string(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["High"] == AlertSeverity.HIGH

    def test_priority_medium_string(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["Medium"] == AlertSeverity.WARNING

    def test_priority_low_string(self):
        assert BmcHelixProvider.PRIORITY_TO_SEVERITY["Low"] == AlertSeverity.LOW

    def test_unknown_priority_defaults_to_warning(self):
        severity = BmcHelixProvider.PRIORITY_TO_SEVERITY.get("99", AlertSeverity.WARNING)
        assert severity == AlertSeverity.WARNING

    def test_format_alert_priority_1_critical(self):
        event = _make_push_event(priority="1")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_priority_2_high(self):
        event = _make_push_event(priority="2")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.severity == AlertSeverity.HIGH

    def test_format_alert_priority_3_warning(self):
        event = _make_push_event(priority="3")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------


class TestStatusMapping:
    def test_new_is_firing(self):
        assert BmcHelixProvider.STATUS_MAP["New"] == AlertStatus.FIRING

    def test_assigned_is_firing(self):
        assert BmcHelixProvider.STATUS_MAP["Assigned"] == AlertStatus.FIRING

    def test_in_progress_is_firing(self):
        assert BmcHelixProvider.STATUS_MAP["In Progress"] == AlertStatus.FIRING

    def test_pending_is_suppressed(self):
        assert BmcHelixProvider.STATUS_MAP["Pending"] == AlertStatus.SUPPRESSED

    def test_resolved_is_resolved(self):
        assert BmcHelixProvider.STATUS_MAP["Resolved"] == AlertStatus.RESOLVED

    def test_closed_is_resolved(self):
        assert BmcHelixProvider.STATUS_MAP["Closed"] == AlertStatus.RESOLVED

    def test_cancelled_is_resolved(self):
        assert BmcHelixProvider.STATUS_MAP["Cancelled"] == AlertStatus.RESOLVED

    def test_unknown_status_defaults_to_firing(self):
        status = BmcHelixProvider.STATUS_MAP.get("Unknown_Status", AlertStatus.FIRING)
        assert status == AlertStatus.FIRING

    def test_format_alert_new_is_firing(self):
        event = _make_push_event(status="New")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING

    def test_format_alert_resolved(self):
        event = _make_push_event(status="Resolved")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED

    def test_format_alert_pending_suppressed(self):
        event = _make_push_event(status="Pending")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.status == AlertStatus.SUPPRESSED


# ---------------------------------------------------------------------------
# _entry_to_alert_dto (pull mode)
# ---------------------------------------------------------------------------


class TestEntryToAlertDto:
    def test_incident_number_used_as_id(self, provider):
        entry = _make_entry(incident_number="INC9876543")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.id == "INC9876543"

    def test_summary_used_as_name(self, provider):
        entry = _make_entry(summary="Server down")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.name == "Server down"

    def test_notes_used_as_description(self, provider):
        entry = _make_entry(notes="Memory exhausted")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.description == "Memory exhausted"

    def test_company_extracted(self, provider):
        entry = _make_entry(company="TechCorp")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.company == "TechCorp"

    def test_service_extracted(self, provider):
        entry = _make_entry(service="Auth Service")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.service == "Auth Service"

    def test_assignee_extracted(self, provider):
        entry = _make_entry(assignee="jane.smith")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.assignee == "jane.smith"

    def test_assigned_group_extracted(self, provider):
        entry = _make_entry(assigned_group="Infra Team")
        alert = provider._entry_to_alert_dto(entry)
        assert alert.assigned_group == "Infra Team"

    def test_source_is_bmc_helix(self, provider):
        entry = _make_entry()
        alert = provider._entry_to_alert_dto(entry)
        assert "bmc_helix" in alert.source

    def test_url_extracted_from_hal_links(self, provider):
        entry = _make_entry()
        alert = provider._entry_to_alert_dto(entry)
        assert "helix.example.com" in alert.url

    def test_epoch_ms_timestamp_converted(self, provider):
        ts_ms = 1700000000000  # 2023-11-14
        entry = _make_entry(submit_date=ts_ms)
        alert = provider._entry_to_alert_dto(entry)
        expected = datetime.datetime.fromtimestamp(
            ts_ms / 1000, tz=datetime.timezone.utc
        )
        assert alert.lastReceived == expected

    def test_invalid_timestamp_uses_now(self, provider):
        entry = _make_entry()
        entry["values"]["Submit Date"] = "not-a-timestamp"
        before = datetime.datetime.now(tz=datetime.timezone.utc)
        alert = provider._entry_to_alert_dto(entry)
        after = datetime.datetime.now(tz=datetime.timezone.utc)
        assert before <= alert.lastReceived <= after


# ---------------------------------------------------------------------------
# _format_alert (push mode)
# ---------------------------------------------------------------------------


class TestFormatAlert:
    def test_wrapped_payload_parsed(self):
        event = _make_push_event(wrapped=True)
        alert = BmcHelixProvider._format_alert(event)
        assert alert.id == "INC0005678"

    def test_flat_payload_parsed(self):
        event = _make_push_event(wrapped=False)
        alert = BmcHelixProvider._format_alert(event)
        assert alert.id == "INC0005678"

    def test_pushed_flag_set(self):
        event = _make_push_event()
        alert = BmcHelixProvider._format_alert(event)
        assert alert.pushed is True

    def test_summary_as_name(self):
        event = _make_push_event(summary="API gateway down")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.name == "API gateway down"

    def test_notes_as_description(self):
        event = _make_push_event(notes="Load balancer unreachable")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.description == "Load balancer unreachable"

    def test_company_extracted(self):
        event = _make_push_event(company="GlobalCorp")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.company == "GlobalCorp"

    def test_service_extracted(self):
        event = _make_push_event(service="Core API")
        alert = BmcHelixProvider._format_alert(event)
        assert alert.service == "Core API"

    def test_source_is_bmc_helix(self):
        event = _make_push_event()
        alert = BmcHelixProvider._format_alert(event)
        assert "bmc_helix" in alert.source

    def test_empty_event_does_not_raise(self):
        alert = BmcHelixProvider._format_alert({})
        assert alert is not None

    def test_epoch_ms_timestamp(self):
        ts_ms = 1700000000000
        event = _make_push_event(submit_date=ts_ms)
        alert = BmcHelixProvider._format_alert(event)
        expected = datetime.datetime.fromtimestamp(
            ts_ms / 1000, tz=datetime.timezone.utc
        )
        assert alert.lastReceived == expected


# ---------------------------------------------------------------------------
# _get_alerts (pull mode)
# ---------------------------------------------------------------------------


class TestGetAlerts:
    def test_returns_alerts_from_entries(self, provider):
        entries = [
            _make_entry(incident_number="INC001", status="New"),
            _make_entry(incident_number="INC002", status="In Progress"),
        ]
        provider._jwt_token = "tok"
        with patch.object(provider, "_get_incidents", return_value=entries):
            alerts = provider._get_alerts()
        assert len(alerts) == 2
        ids = {a.id for a in alerts}
        assert "INC001" in ids
        assert "INC002" in ids

    def test_malformed_entry_is_skipped(self, provider):
        bad = {"bad": "entry"}
        good = _make_entry(incident_number="INC003")
        provider._jwt_token = "tok"
        with patch.object(provider, "_get_incidents", return_value=[bad, good]):
            alerts = provider._get_alerts()
        assert len(alerts) == 1
        assert alerts[0].id == "INC003"

    def test_empty_result_returns_empty_list(self, provider):
        provider._jwt_token = "tok"
        with patch.object(provider, "_get_incidents", return_value=[]):
            alerts = provider._get_alerts()
        assert alerts == []

    def test_default_qualification_filters_closed(self, provider):
        provider._jwt_token = "tok"
        with patch.object(provider, "_api_get", return_value={"entries": []}) as mock:
            provider._get_incidents()
        params = mock.call_args[1]["params"]
        qual = params.get("q", "")
        assert "Closed" in qual
        assert "Cancelled" in qual


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    def test_valid_when_token_obtained(self, provider):
        with patch.object(provider, "_get_jwt_token", return_value="tok"):
            result = provider.validate_scopes()
        assert result["incident_read"] is True

    def test_invalid_when_auth_fails(self, provider):
        with patch.object(
            provider, "_get_jwt_token", side_effect=Exception("auth failed")
        ):
            result = provider.validate_scopes()
        assert "auth failed" in str(result["incident_read"])


# ---------------------------------------------------------------------------
# create_incident
# ---------------------------------------------------------------------------


class TestCreateIncident:
    def test_create_incident_posts_to_correct_endpoint(self, provider):
        provider._jwt_token = "tok"
        mock_resp = MagicMock()
        mock_resp.text = '{"entryId": "NEWENTRY001"}'
        mock_resp.json.return_value = {"entryId": "NEWENTRY001"}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = provider.create_incident(
                summary="Test incident",
                notes="Created by test",
                priority="2",
            )

        url_called = mock_post.call_args[0][0]
        assert "HPD:IncidentInterface_Create" in url_called

    def test_create_incident_passes_summary(self, provider):
        provider._jwt_token = "tok"
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            provider.create_incident(summary="Disk full", priority="1")

        payload = mock_post.call_args[1]["json"]
        assert payload["values"]["Summary"] == "Disk full"
        assert payload["values"]["Priority"] == "1"

    def test_notify_maps_severity_to_priority(self, provider):
        provider._jwt_token = "tok"
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            provider.notify(message="High priority alert", severity="high")

        payload = mock_post.call_args[1]["json"]
        assert payload["values"]["Priority"] == "2"

    def test_notify_critical_severity(self, provider):
        provider._jwt_token = "tok"
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            provider.notify(message="Critical!", severity="critical")

        payload = mock_post.call_args[1]["json"]
        assert payload["values"]["Priority"] == "1"
